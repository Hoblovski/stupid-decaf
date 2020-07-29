import sys
from antlr4 import *
from generated.MiniDecafLexer import MiniDecafLexer
from generated.MiniDecafParser import MiniDecafParser
#from MiniDecafVisitor import MiniDecafVisitor

def main(argv):
    if len(argv) != 2:
        print(f"Usage: ${argv[0]} INPUT")
        exit(1)

    input_stream = FileStream(argv[1])
    lexer = MiniDecafLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = MiniDecafParser(token_stream)
    tree = parser.top()
    print(tree.toStringTree(recog=parser))

if __name__ == '__main__':
    main(sys.argv)
