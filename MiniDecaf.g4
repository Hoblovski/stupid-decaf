grammar MiniDecaf;

import CommonLex;

atom
    : Integer
    ;

add
    : atom (AddOp atom)*
    ;


top
    : add EOF
    ;
