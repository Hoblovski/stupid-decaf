import sys
from antlr4 import *
from generated.MiniDecafLexer import MiniDecafLexer
from generated.MiniDecafParser import MiniDecafParser
from generated.MiniDecafVisitor import MiniDecafVisitor

def text(x):
    if x is not None:
        return str(x.getText())

class AsmEmitter:
    def __init__(self, output_file=None):
        if output_file is None:
            self._f = sys.stdout
        else:
            self._f = open(filename, "w")

    def emit(self, x:str):
        print(x, file=self._f)

    def __call__(self, x:str):
        self.emit(x)

    def close(self):
        if self._f is not sys.stdout:
            self._f.close()

class RISCVAsmGen(MiniDecafVisitor):
    def __init__(self, emitter):
        self._E = emitter
        self.offsets = {}
        self.nlabels = 0

    def createLabel(self):
        x = f"_L{self.nlabels}"
        self.nlabels += 1
        return x

    def push(self, x):
        if type(x) is str:
            x = int(x)
        if type(x) is int:
            self._E(
f"""# push {x}
\tli t0, {x}
\taddi sp, sp, -8
\tsd t0, 0(sp)""")

    def binary(self, op):
        try:
            op = { "+": "add", "-": "sub", "*": "mul", "/": "div" }[op]
        except: return
        self._E(
f"""# {op}
\tld t1, 0(sp)
\tld t0, 8(sp)
\t{op} t0, t0, t1
\taddi sp, sp, 8
\tsd t0, 0(sp)""")

    def unary(self, op):
        try:
            op = { "-": "neg" }[op]
        except: return
        self._E(
f"""# {op}
\tld t0, 0(sp)
\t{op} t0, t0
\tsd t0, 0(sp)""")

    def relational(self, op):
        if op not in { "==", "!=", "<", "<=", ">", ">=" }:
            return
        self._E(
f"""# {op}
\tld t1, 0(sp)
\tld t0, 8(sp)
\taddi sp, sp, 8""")

        try:
            op = { "==": "seqz", "!=": "snez" }[op]
            self._E(
f"""\tsub t0, t0, t1
\t{op} t0, t0
\tsd t0, 0(sp)""")
            return
        except: pass

        try:
            x = op in { "<=", ">=" }
            op = { "<": "slt", ">=": "slt", ">": "sgt", "<=": "sgt" }[op]
            self._E(f"\t{op} t0, t0, t1")
            if x:
                self._E(f"\txori t0, t0, 1")
            self._E(f"\tsd t0, 0(sp)")
            return
        except: pass

    def store(self, var):
        self._E(
f"""# store {var}
\tld t0, 0(sp)
\taddi sp, sp, 8
\tsd t0, {self.offsets[var]}(fp)""")

    def load(self, var):
        self._E(
f"""# load {var}
\tld t0, {self.offsets[var]}(fp)
\taddi sp, sp, -8
\tsd t0, 0(sp)""")


    def visitAtomInteger(self, ctx:MiniDecafParser.AtomIntegerContext):
        self.push(text(ctx))

    def visitAtomIdent(self, ctx:MiniDecafParser.AtomIdentContext):
        if text(ctx) not in self.offsets:
            raise Exception(f"{text(ctx)} used before define")
        self.load(text(ctx))

    def visitCUnary(self, ctx:MiniDecafParser.CUnaryContext):
        self.visitChildren(ctx)
        self.unary(text(ctx.unaryOp()))

    def visitCAdd(self, ctx:MiniDecafParser.AddContext):
        self.visitChildren(ctx)
        self.binary(text(ctx.addOp()))

    def visitCMul(self, ctx:MiniDecafParser.MulContext):
        self.visitChildren(ctx)
        self.binary(text(ctx.mulOp()))

    def visitCRel(self, ctx:MiniDecafParser.CRelContext):
        self.visitChildren(ctx)
        self.relational(text(ctx.relOp()))

    def visitAsgn(self, ctx:MiniDecafParser.AsgnContext):
        self._E(f"# [Asgn]")
        v = text(ctx.lhs())
        if v not in self.offsets:
            o = 8 * len(self.offsets)
            self.offsets[v] = o
            self._E(f"# {v} !-> {o}")
            self._E("\taddi sp, sp, -8")
        self.visitChildren(ctx)
        self.store(text(ctx.lhs()))

    def visitRet(self, ctx:MiniDecafParser.RetContext):
        self._E(f"# [Ret]")
        self.visitChildren(ctx)
        self._E(f"# ret")
        self._E("\tbeqz zero, main_exit")

    def visitIf(self, ctx:MiniDecafParser.IfContext):
        self._E(f"# [If]")
        ctx.th.in_label = self.createLabel()
        ctx.th.out_label = self.createLabel()
        if ctx.el is not None:
            ctx.el.in_label = self.createLabel()
            ctx.el.out_label = ctx.th.out_label

        self.visitExpr(ctx.expr())
        self._E(
f"""# if-jump
\tld t0, 0(sp)
\taddi sp, sp, 8
\tbnez t0, {ctx.th.in_label}""")
        if ctx.el is not None:
            self._E(f"\tbeqz zero, {ctx.el.in_label}")
        else:
            self._E(f"\tbeqz zero, {ctx.th.out_label}")
        self.visitStmtLabeled(ctx.th)
        if ctx.el is not None: self.visitStmtLabeled(ctx.el)
        self._E(f"{ctx.th.out_label}:")

    def visitStmtLabeled(self, ctx:MiniDecafParser.StmtLabeledContext):
        self._E(f"{ctx.in_label}:")
        self.visitChildren(ctx)
        self._E(f"\tbeqz zero, {ctx.out_label}")

    def visitTop(self, ctx:MiniDecafParser.TopContext):
        self._E(
""".global main
main:
\tmv fp, sp
# end entry\n""")
        self.visitChildren(ctx)
        self._E(
"""# begin exit
main_exit:
\tld a0, 0(sp)
\taddi sp, sp, 8
\tret\n""")



def main(argv):
    if len(argv) != 2:
        print(f"Usage: ${argv[0]} INPUT")
        exit(1)

    input_stream = FileStream(argv[1])
    lexer = MiniDecafLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = MiniDecafParser(token_stream)
    tree = parser.top()

    visitor = RISCVAsmGen(AsmEmitter())
    visitor.visit(tree)

if __name__ == '__main__':
    main(sys.argv)
