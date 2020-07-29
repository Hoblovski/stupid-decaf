import sys
from antlr4 import *
from generated.MiniDecafLexer import MiniDecafLexer
from generated.MiniDecafParser import MiniDecafParser
from generated.MiniDecafListener import MiniDecafListener

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


class RISCVAsmGen(MiniDecafListener):
    def __init__(self, emitter):
        self._E = emitter

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
        except:
            return
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
        except:
            return
        self._E(
f"""# {op}
\tld t0, 0(sp)
\t{op} t0, t0
\tsd t0, 0(sp)""")


    def exitAtomInteger(self, ctx:MiniDecafParser.AtomIntegerContext):
        self.push(text(ctx))

    def exitCUnary(self, ctx:MiniDecafParser.CUnaryContext):
        self.unary(text(ctx.unaryOp()))

    def exitCAdd(self, ctx:MiniDecafParser.AddContext):
        self.binary(text(ctx.addOp()))

    def exitCMul(self, ctx:MiniDecafParser.MulContext):
        self.binary(text(ctx.mulOp()))

    def enterTop(self, ctx:MiniDecafParser.TopContext):
        self._E(
""".global main
main:
\tmv s0, sp
# end entry""")

    def exitTop(self, ctx:MiniDecafParser.TopContext):
        self._E(
"""# begin exit
\tld a0, 0(sp)
\taddi sp, sp, 8
\tret""")



def main(argv):
    if len(argv) != 2:
        print(f"Usage: ${argv[0]} INPUT")
        exit(1)

    input_stream = FileStream(argv[1])
    lexer = MiniDecafLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = MiniDecafParser(token_stream)
    tree = parser.top()

    listener = RISCVAsmGen(AsmEmitter())
    walker = ParseTreeWalker()
    walker.walk(listener, tree)

if __name__ == '__main__':
    main(sys.argv)
