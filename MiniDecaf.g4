grammar MiniDecaf;

import CommonLex;

atom
    : Integer # AtomInteger
    | Ident # AtomIdent
    | '(' expr ')' # AtomParen
    ;

unary
    : atom # tUnary
    | unaryOp atom # cUnary
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

lhs
    : Ident
    ;

stmt
    : lhs '=' rel ';'   # Asgn
    | 'return' expr ';' # Ret
    ;

top
    : stmt* EOF
    ;

unaryOp
    : '-'
    ;

addOp
    : '+' | '-'
    ;

mulOp
    : '*' | '/'
    ;

relOp
    : '==' | '!=' | '<' | '>' | '<=' | '>='
    ;
