import sys
from copy import deepcopy
from antlr4 import *
from generated.MiniDecafLexer import MiniDecafLexer
from generated.MiniDecafParser import MiniDecafParser
from generated.MiniDecafVisitor import MiniDecafVisitor

NREGARGS = 8

def text(x):
    if x is not None:
        return str(x.getText())

class AsmEmitter:
    def __init__(self, output_file=None):
        if output_file is None:
            self._f = sys.stdout
        else:
            self._f = open(output_file, "w")

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

class Typ:
    def __init__(self, base="int", ptrLvs=0, arrDims=[]):
        self.base = base
        self.ptrLvs = ptrLvs
        self.arrDims = arrDims

    def __eq__(self, oth):
        if self.base != oth.base: return False
        if self.ptrLvs != oth.ptrLvs: return False
        if self.arrDims != oth.arrDims: return False
        return True

    def wrapPtr(self):
        oth = deepcopy(self)
        oth.ptrLvs += 1
        return oth

    def unwrapPtr(self):
        oth = deepcopy(self)
        assert oth.ptrLvs > 0
        oth.ptrLvs -= 1
        return oth

    def sizeof(self):
        if not self.isArr():
            return 8
        else:
            return self.arrBase().sizeof() * self.arrElemCnt()

    def isPtr(self):
        return self.ptrLvs > 0

    def isArr(self):
        return len(self.arrDims) > 0

    def arrElemCnt(self):
        assert len(self.arrDims) > 0
        return prod(self.arrDims)

    def arrBase(self):
        oth = deepcopy(self)
        oth.arrDims = []
        return oth

    def arrNextLevel(self):
        oth = deepcopy(self)
        oth.arrDims = oth.arrDims[1:]
        return oth

    def toArr(self, arrDims):
        oth = deepcopy(self)
        oth.arrDims = arrDims
        return oth

    def __str__(self):
        return self.base + "*"*self.ptrLvs + ''.join(map(lambda d: f"[{d}]", self.arrDims))

intTy = Typ(base="int")

def typeRule(rule):
    def f(*args):
        retTy = rule(*args)
        if type(retTy) is str:
            raise Exception(retTy)
        return retTy
    return f

@typeRule
def unaryIntRule(ty):
    if ty == intTy: return intTy
    return f"unaryInt: expected int, given {ty}"

@typeRule
def binaryIntRule(ty1, ty2):
    if ty1 == ty2 == intTy: return intTy
    return f"binaryInt: expected <int, int>, given <{ty1}, {ty2}>"

@typeRule
def binaryPtrArithRule(ty1, ty2):
    if ty1 == intTy and ty2.isPtr(): return ty2
    if ty2 == intTy and ty1.isPtr(): return ty1
    return f"unaryPtrArith: expected ptrArith, given <{ty1}, {ty2}>"

@typeRule
def sameType(ty1, ty2):
    if ty1 == ty2: return intTy
    return f"sameType: expected two identical types, given <{ty1}, {ty2}>"

@typeRule
def anyRuleCanApply(*rules):
    def r(*args):
        errs = []
        for rule in rules:
            try:
                return rule(*args)
            except Exception as e:
                errs += [str(e)]
        return "anyRuleCanApply: all alternatives failed" + '\n  '.join([""]+errs)
    return r

@typeRule
def derefRule(ty):
    if ty.isPtr(): return ty.unwrapPtr()
    return f"derefRule: ptr expected, but {ty} given"


def prod(l):
    p = 1
    for i in l: p *= i
    return p

class RISCVAsmGen(MiniDecafVisitor):
    def __init__(self, emitter):
        self._E = emitter
        self.voff = [{}] # voff[-1][v] =x : v lies at x(fp)
        self.vtyp = [{}] # int**: (int, 2), int: (int, 0), char*: (char, 1)
        self.etyp = {}
        self.stacksz = [0]
        self.nlabels = 0
        self.curfunc = None
        self.funcinfo = {} # (argsTy:list, retTy:Typ)

    def checkTypeCoercion(self, ty1, ty2, msg=None):
        if msg is None:
            msg = f"cannot assign {ty2} to {ty1}"
        if not ty1 == ty2:
            raise Exception(msg)

    def checkAsgn(self, ty1, ty2, msg=None):
        self.checkTypeCoercion(ty1, ty2, msg)
        if ty1.isArr():
            raise Exception("cannot assign to an array")

    def insert_var(self, v, ty):
        self.stacksz[-1] += ty.sizeof()
        self.voff[-1][v] = - self.stacksz[-1]
        self.vtyp[-1][v] = ty
        self._E(f"# {v} -> {self.voff[-1][v]}")

    def enter_scope(self):
        self.voff += [deepcopy(self.voff[-1])]
        self.vtyp += [deepcopy(self.vtyp[-1])]
        self.stacksz += [self.stacksz[-1]]
        self.voff[-1] = self.voff[-1]

    def exit_scope(self):
        szdiff = self.stacksz[-1] - self.stacksz[-2]
        self.voff.pop()
        self.vtyp.pop()
        self.stacksz.pop()
        self._E(f"""# exit scope
\taddi sp, sp, {szdiff}""")

    def createLabel(self):
        x = f"_L{self.nlabels}"
        self.nlabels += 1
        return x

    def push(self, x):
        try:
            x = int(x)
            return f"""# push {x}
\tli t1, {x}
\taddi sp, sp, -8
\tsd t1, 0(sp)"""
        except:
            return f"""# push {x}
\taddi sp, sp, -8
\tsd {x}, 0(sp)"""

    def pop(self, x):
        try:
            x = int(x)
            return f"""# pop {x} * 8
\taddi sp, sp, {8*x}"""
        except:
            return f"""# pop {x}
\tld {x}, 0(sp)
\taddi sp, sp, 8"""


    def binary(self, op, lhs, rhs):
        opstr = { "+": "add", "-": "sub", "*": "mul", "/": "div", "%": "rem" }[op]

        prepareSizeof = ""
        prepareRhs = "\tld t2, 0(sp)"
        prepareLhs = "\tld t1, 8(sp)"

        try: # stupid C. ptrArith offset fixup
            assert op in {"+", "-"}
            rule = binaryPtrArithRule
            lhsTy = self.etyp[lhs]
            rhsTy = self.etyp[rhs]
            rule(lhsTy, rhsTy)
            if lhsTy == intTy:
                prepareSizeof = f"\tli t3, {rhsTy.sizeof()}"
                prepareLhs += f"\n\tmul t1, t1, t3"
            else:
                prepareSizeof = f"\tli t3, {lhsTy.sizeof()}"
                prepareRhs += f"\n\tmul t2, t2, t3"
        except:
            rule = binaryIntRule

        self._E(
f"""# {op}
{prepareSizeof}
{prepareRhs}
{prepareLhs}
\t{opstr} t1, t1, t2
\taddi sp, sp, 8
\tsd t1, 0(sp)""")

        retTy = rule(self.etyp[lhs], self.etyp[rhs])
        return retTy

    def unary(self, op, lhs):
        try:
            op = { "-": "neg" }[op]
            rule = unaryIntRule
            self._E(f"""# {op}
\tld t1, 0(sp)
\t{op} t1, t1
\tsd t1, 0(sp)""")
        except KeyError: pass

        try:
            op = { "*": "deref" }[op]
            rule = derefRule
            self._E(f"""# {op}
{self.pop("t1")}
\tld t1, 0(t1)
{self.push("t1")}""")
        except KeyError: pass

        try:
            op = { "&": "addrof" }[op]
            var = text(lhs)
            if var not in self.voff[-1]:
                raise Exception(f"cannot take address of {var}")
            self._E(f"""# {op}
\tli t1, {self.voff[-1][var]}
\tadd t1, t1, fp
{self.push("t1")}""")
            return self.vtyp[-1][var].wrapPtr()
        except KeyError: pass

        return rule(self.etyp[lhs])

    def relational(self, op, lhs, rhs):
        assert op in { "==", "!=", "<", "<=", ">", ">=" }
        rule = sameType

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
            return rule(self.etyp[lhs], self.etyp[rhs])
        except KeyError: pass

        try:
            x = op in { "<=", ">=" }
            op = { "<": "slt", ">=": "slt", ">": "sgt", "<=": "sgt" }[op]
            self._E(f"\t{op} t1, t1, t2")
            if x:
                self._E(f"\txori t1, t1, 1")
            self._E(f"\tsd t1, 0(sp)")
            return rule(self.etyp[lhs], self.etyp[rhs])
        except KeyError: pass

    def store(self, var):
        self._E(
f"""# store {var} ({self.voff[-1][var]})
\tld t1, 0(sp)
\taddi sp, sp, 8
\tsd t1, {self.voff[-1][var]}(fp)""")

    def load(self, var):
        if self.vtyp[-1][var].isArr():
            self._E(
f"""# load {var}
\tli t1, {self.voff[-1][var]}
\tadd t1, t1, fp
{self.push("t1")}""")
        else:
            self._E(
f"""# load {var}
\tld t1, {self.voff[-1][var]}(fp)
{self.push("t1")}""")

    def prologue(self, params, paramTys):
        self._E(
f""".global {self.curfunc}
{self.curfunc}:
{self.push("ra")}
{self.push("fp")}
\tmv fp, sp""")
        self.enter_scope()
        for i, (param, ty) in enumerate(zip(params, paramTys)):
            p = text(param)
            self.insert_var(p, ty)
            if i < NREGARGS:
                self._E(self.push(f"a{i}"))
            else:
                self._E(# XXX: forbid array args, arg could only be 8 bytes
f"""\tld t1, {8 * (len(params) - i + 1)}(fp)
{self.push("t1")}""")
        self._E("# end entry\n")

    def epilogue(self):
        self.exit_scope()
        self._E(
f"""\n# begin exit
{self.curfunc}_exit:
\tld a0, 0(sp)
\tmv sp, fp
\tld fp, 0(sp)
\taddi sp, sp, 8
\tld ra, 0(sp)
\taddi sp, sp, 8
\tjr ra\n""")
        self._E("#"*78)

    def visitAtomInteger(self, ctx:MiniDecafParser.AtomIntegerContext):
        self._E(self.push(text(ctx)))
        self.etyp[ctx] = intTy

    def visitAtomCast(self, ctx:MiniDecafParser.AtomCastContext):
        ty = ctx.ty().accept(self)
        self.visitExpr(ctx.expr())
        self.etyp[ctx] = ty

    def visitAtomArray(self, ctx:MiniDecafParser.AtomArrayContext):
        self.visitChildren(ctx)
        nextTy = self.etyp[ctx.atom()].arrNextLevel()
        self._E(
f"""# (array indexing rd)
{self.pop("t2")}
\tli t3, {nextTy.sizeof()}
\tmul t2, t2, t3
{self.pop("t1")}
\tadd t1, t1, t2""")
        if not nextTy.isArr(): # last level: load the value
            self._E(f"""ld t1, 0(t1)
{self.push("t1")}""")
        else:
            self._E(self.push("t1"))
        self.etyp[ctx] = nextTy

    def visitAtomIdent(self, ctx:MiniDecafParser.AtomIdentContext):
        if text(ctx) not in self.voff[-1]:
            raise Exception(f"{text(ctx)} used before define")
        self.load(text(ctx))
        self.etyp[ctx] = self.vtyp[-1][text(ctx)]

    def visitAtomCall(self, ctx:MiniDecafParser.AtomCallContext):
        args = ctx.exprList().expr()
        name = text(ctx.Ident())
        if name not in self.funcinfo:
            raise Exception(f"{name} function called before define")
        paramTys = self.funcinfo[name][0]
        retTy = self.funcinfo[name][1]
        if len(args) != len(paramTys):
            raise Exception(f"{name} expects {len(paramTys)} args but {len(args)} are provided")
        self._E(f"# call {name}")
        for i, (arg, paramTy) in enumerate(zip(args, paramTys)):
            self.visitExpr(arg)
            self.checkTypeCoercion(self.etyp[arg], paramTy,
                f"parameter type: {paramTy} expect but {self.etyp[arg]} found")
            if i < NREGARGS:
                self._E(
f"""# param {i}
\tld a{i}, 0(sp)
\taddi sp, sp, 8""")

        self._E(
f"""\tcall {name}
addi sp, sp, {8 * max(0, len(args) - NREGARGS)}
{self.push("a0")}""")
        self.etyp[ctx] = retTy

    def visitCUnary(self, ctx:MiniDecafParser.CUnaryContext):
        op = text(ctx.unaryOp())
        if op != '&':
            self.visitChildren(ctx)
        self.etyp[ctx] = self.unary(op, ctx.unary())

    def visitCAdd(self, ctx:MiniDecafParser.AddContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.binary(text(ctx.addOp()), ctx.add(), ctx.mul())

    def visitCMul(self, ctx:MiniDecafParser.MulContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.binary(text(ctx.mulOp()), ctx.mul(), ctx.unary())

    def visitCRel(self, ctx:MiniDecafParser.CRelContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.relational(text(ctx.relOp()), ctx.add(0), ctx.add(1))

    def visitAsgn(self, ctx:MiniDecafParser.AsgnContext):
        self._E(f"# [Asgn]")
        self.visitChildren(ctx) # push addr(lhs); val(rhs)
        self.checkAsgn(self.etyp[ctx.lhs()], self.etyp[ctx.expr()]);
        self._E(f"""{self.pop("t1")}
{self.pop("t2")}
\tsd t1, 0(t2)""")

    def visitRet(self, ctx:MiniDecafParser.RetContext):
        self._E(f"# [Ret]")
        self.visitChildren(ctx)
        rule = sameType
        rule(self.etyp[ctx.expr()], self.funcinfo[self.curfunc][1])
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
        rule = unaryIntRule
        rule(self.etyp[ctx.expr()])
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

    def visitBlock(self, ctx:MiniDecafParser.BlockContext):
        self.enter_scope()
        self.visitChildren(ctx)
        self.exit_scope()

    def visitFunc(self, ctx:MiniDecafParser.FuncContext):
        name = text(ctx.Ident())
        params = ctx.paramList().Ident()
        paramTys = map(lambda x: x.accept(self), ctx.paramList().ty())
        self.curfunc = name
        self.funcinfo[name] = (
                list(map(lambda x: x.accept(self), ctx.paramList().ty())),
                ctx.ty().accept(self))
        self.prologue(params, paramTys)
        for s in ctx.stmt(): s.accept(self)
        self.epilogue()

    def visitExprStmt(self, ctx:MiniDecafParser.ExprStmtContext):
        self.visitChildren(ctx)
        self._E(self.pop(1))

    def visitIntTy(self, ctx:MiniDecafParser.IntTyContext):
        return intTy

    def visitPtrTy(self, ctx:MiniDecafParser.PtrTyContext):
        ty = ctx.ty().accept(self)
        return ty.wrapPtr()

    def visitDecl(self, ctx:MiniDecafParser.DeclContext):
        self._E("# [Decl]")
        ty = ctx.ty().accept(self)
        expr = ctx.expr()
        dims = [int(text(x)) for x in ctx.Integer()]
        if len(dims) > 0:
            elemsz = ty.sizeof()
            ty = ty.toArr(dims)
            self.insert_var(text(ctx.Ident()), ty)
            self._E(f"\taddi sp, sp, {-ty.sizeof()}")
            for i in range(ty.arrElemCnt()):
                self._E(f"\tsd zero, {i*elemsz}(sp)")
        else:
            self.insert_var(text(ctx.Ident()), ty)
            if expr is not None:
                self.visitExpr(expr)
                self.checkAsgn(ty, self.etyp[expr])
            else:
                self._E(self.push(0))

    def visitTop(self, ctx:MiniDecafParser.TopContext):
        for f in ctx.func():
            f.accept(self)

        self.curfunc = "main"
        self.funcinfo["main"] = ([], intTy)
        self.prologue([], [])
        for s in ctx.stmt():
            s.accept(self)
        self.epilogue()

    def visitTUnary(self, ctx:MiniDecafParser.TUnaryContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.etyp[ctx.atom()]

    def visitTMul(self, ctx:MiniDecafParser.TMulContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.etyp[ctx.unary()]

    def visitTAdd(self, ctx:MiniDecafParser.TAddContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.etyp[ctx.mul()]

    def visitTRel(self, ctx:MiniDecafParser.TRelContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.etyp[ctx.add()]

    def visitAtomParen(self, ctx:MiniDecafParser.AtomParenContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.etyp[ctx.expr()]

    def visitExpr(self, ctx:MiniDecafParser.ExprContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.etyp[ctx.rel()]

    def visitIdentLhs(self, ctx:MiniDecafParser.IdentLhsContext):
        v = text(ctx)
        if v not in self.voff[-1]:
            raise Exception(f"variable {v} used before declaration")
        self._E(f"""\tli t1, {self.voff[-1][v]}
\tadd t1, t1, fp
{self.push("t1")}""")
        self.etyp[ctx] = self.vtyp[-1][v]

    def visitDerefLhs(self, ctx:MiniDecafParser.DerefLhsContext):
        self.visitChildren(ctx)
        self.etyp[ctx] = self.etyp[ctx.expr()].unwrapPtr()

    def visitArrayLhs(self, ctx:MiniDecafParser.ArrayLhsContext):
        self.visitChildren(ctx)
        nextTy = self.etyp[ctx.lhs()].arrNextLevel()
        self._E(
f"""# (array indexing wr)
{self.pop("t2")}
\tli t3, {nextTy.sizeof()}
\tmul t2, t2, t3
{self.pop("t1")}
\tadd t1, t1, t2
{self.push("t1")}""")
        self.etyp[ctx] = nextTy

def main(argv):
    if len(argv) != 2:
        print(f"Usage: ${argv[0]} INPUT")
        exit(1)

    input_stream = FileStream(argv[1])
    lexer = MiniDecafLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = MiniDecafParser(token_stream)
    tree = parser.top()

    visitor = RISCVAsmGen(AsmEmitter('output.s'))
    visitor.visit(tree)

if __name__ == '__main__':
    main(sys.argv)
