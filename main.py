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


# frame layout
#        sp --------------> + ------------------------ +
#                           | temp in computing expr   |
#        sp when enter stmt + ------------------------ +
#                           | local vars (args first)  |
#        fp --------------> + ------------------------ +
#                           | fp                       |
#                           + ------------------------ +
#                           | ra                       |
#                           + ------------------------ +


class RISCVAsmGen(MiniDecafVisitor):
    def __init__(self, emitter):
        self._E = emitter
        self.offsets = {}
        self.nlabels = 0
        self.curfunc = None
        self.funcinfo = {} # nargs

    def insert_var(self, v):
        self.offsets[v] = -8 * (1 + len(self.offsets))
        return self.offsets[v]

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
\tli t1, {x}
\taddi sp, sp, -8
\tsd t1, 0(sp)""")

    def binary(self, op):
        try:
            op = { "+": "add", "-": "sub", "*": "mul", "/": "div", "%": "rem" }[op]
        except: return
        self._E(
f"""# {op}
\tld t2, 0(sp)
\tld t1, 8(sp)
\t{op} t1, t1, t2
\taddi sp, sp, 8
\tsd t1, 0(sp)""")

    def unary(self, op):
        try:
            op = { "-": "neg" }[op]
        except: return
        self._E(
f"""# {op}
\tld t1, 0(sp)
\t{op} t1, t1
\tsd t1, 0(sp)""")

    def relational(self, op):
        if op not in { "==", "!=", "<", "<=", ">", ">=" }:
            return
        self._E(
f"""# {op}
\tld t2, 0(sp)
\tld t1, 8(sp)
\taddi sp, sp, 8""")

        try:
            op = { "==": "seqz", "!=": "snez" }[op]
            self._E(
f"""\tsub t1, t1, t2
\t{op} t1, t1
\tsd t1, 0(sp)""")
            return
        except: pass

        try:
            x = op in { "<=", ">=" }
            op = { "<": "slt", ">=": "slt", ">": "sgt", "<=": "sgt" }[op]
            self._E(f"\t{op} t1, t1, t2")
            if x:
                self._E(f"\txori t1, t1, 1")
            self._E(f"\tsd t1, 0(sp)")
            return
        except: pass

    def store(self, var):
        self._E(
f"""# store {var}
\tld t1, 0(sp)
\taddi sp, sp, 8
\tsd t1, {self.offsets[var]}(fp)""")

    def load(self, var):
        self._E(
f"""# load {var}
\tld t1, {self.offsets[var]}(fp)
\taddi sp, sp, -8
\tsd t1, 0(sp)""")

    def prologue(self, name, params):
        self._E(
f""".global {name}
{name}:
\taddi sp, sp, -8
\tsd ra, 0(sp)
\taddi sp, sp, -8
\tsd fp, 0(sp)
\tmv fp, sp""")
        self.offsets = {}
        for i, param in enumerate(params):
            p = text(param)
            self.insert_var(p)
            self._E(
f"""\taddi sp, sp, -8
\tsd a{i}, {self.offsets[p]}(fp)""")
            # TODO: more args
        self._E("# end entry\n")

    def epilogue(self, name):
        self._E(
f"""\n# begin exit
{name}_exit:
\tld a0, 0(sp)
\tmv sp, fp
\tld fp, 0(sp)
\taddi sp, sp, 8
\tld ra, 0(sp)
\taddi sp, sp, 8
\tjr ra\n""")
        self._E("#"*78)

    def visitAtomInteger(self, ctx:MiniDecafParser.AtomIntegerContext):
        self.push(text(ctx))

    def visitAtomIdent(self, ctx:MiniDecafParser.AtomIdentContext):
        if text(ctx) not in self.offsets:
            raise Exception(f"{text(ctx)} used before define")
        self.load(text(ctx))

    def visitAtomCall(self, ctx:MiniDecafParser.AtomCallContext):
        args = ctx.exprList().expr()
        name = text(ctx.Ident())
        if len(args) != self.funcinfo[name][0]:
            raise Exception(f"{name} expects {self.funcinfo[name][0]} args but {len(args)} are provided")
        self._E(f"# call {name}")
        for i, arg in enumerate(args):
            self.visitExpr(arg)
            if i < 8:
                self._E(
f"""# param {i}
\tld a{i}, 0(sp)
\taddi sp, sp, 8""")
            else:
                assert False # TODO: more args
        self._E(
f"""\tcall {name}
\taddi sp, sp, -8
\tsd a0, 0(sp)""")

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
            o = self.insert_var(v)
            self._E(f"# {v} !-> {o}")
            self._E("\taddi sp, sp, -8")
        self.visitChildren(ctx)
        self.store(text(ctx.lhs()))

    def visitRet(self, ctx:MiniDecafParser.RetContext):
        self._E(f"# [Ret]")
        self.visitChildren(ctx)
        self._E(f"# ret")
        self._E(f"\tbeqz zero, {self.curfunc}_exit")

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
\tld t1, 0(sp)
\taddi sp, sp, 8
\tbnez t1, {ctx.th.in_label}""")
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

    def visitFunc(self, ctx:MiniDecafParser.FuncContext):
        name = text(ctx.Ident())
        params = ctx.identList().Ident()
        self.curfunc = name
        self.funcinfo[name] = (len(params),)
        self.prologue(name, params)
        for s in ctx.stmt(): s.accept(self)
        self.epilogue(name)

    def visitTop(self, ctx:MiniDecafParser.TopContext):
        for f in ctx.func():
            f.accept(self)

        self.curfunc = "main"
        self.prologue("main", [])
        for s in ctx.stmt(): s.accept(self)
        self.epilogue("main")

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
