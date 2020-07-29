grammar MiniDecaf;

import CommonLex;

atom
    : Integer # AtomInteger
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

expr
    : add
    ;

top
    : expr EOF
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

