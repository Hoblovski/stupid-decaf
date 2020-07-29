lexer grammar CommonLex;

Integer: Digit+;

Whitespace: [ \t\n\r]+ -> skip;

fragment Digit: [0-9];
