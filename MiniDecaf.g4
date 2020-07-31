grammar MiniDecaf;

import CommonLex;

atom
    : Integer # AtomInteger
    | Ident # AtomIdent
    | '(' expr ')' # AtomParen
    | Ident '(' exprList ')' # AtomCall
    | atom '[' expr ']' # AtomArray
    | '(' ty ')' expr # AtomCast
    ;

unary
    : atom # tUnary
    | unaryOp unary # cUnary
    ;

mul
    : unary # tMul
    | mul mulOp unary # cMul
    ;

add
    : mul # tAdd
    | add addOp mul # cAdd
    ;

rel
    : add # tRel
    | add relOp add # cRel  // to avoid quirks, forbid chained relops
    ;

expr
    : rel
    ;

exprList
    : (expr (',' expr)*)?
    ;

lhs
    : Ident # IdentLhs
    | '*' expr # DerefLhs
    | lhs ('[' expr ']') # ArrayLhs
    ;

stmtLabeled
    : stmt
    ;

decl
    : ty Ident ('=' expr)? ';'
    | ty Ident ('[' Integer ']')* ';'
    ;

stmt
    : lhs '=' expr ';'   # Asgn
    | decl # DeclStmt
    | expr ';' # ExprStmt
    | 'return' expr ';' # Ret
    | 'if' '(' expr ')' th=stmtLabeled ('else' el=stmtLabeled)? # If
    | '{' stmt* '}' # block
    ;

paramList
    : (ty Ident (',' ty Ident)*)?
    ;

func
    : ty Ident '(' paramList ')' '{' stmt* '}'
    ;

top
    : func* stmt* EOF
    ;

ty
    : 'int' # IntTy
    | ty ptr='*' # PtrTy
    ;

unaryOp
    : '-' | '&' | '*'
    ;

addOp
    : '+' | '-'
    ;

mulOp
    : '*' | '/' | '%'
    ;

relOp
    : '==' | '!=' | '<' | '>' | '<=' | '>='
    ;
