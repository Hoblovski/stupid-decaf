lexer grammar CommonLex;

Integer: Digit+;
AddOp: '+' | '-';

Whitespace: [ \t\n\r]+ -> skip;

fragment Digit: [0-9];
