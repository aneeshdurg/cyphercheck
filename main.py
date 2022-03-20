import sys
from antlr4 import *
from CypherLexer import CypherLexer
from CypherParser import CypherParser

def main(argv):
    input_stream = FileStream(argv[1])
    lexer = CypherLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CypherParser(stream)
    tree = parser.oC_Cypher()

    query = tree.oC_Statement().oC_Query()
    print(
        query.oC_RegularQuery(),
        query.oC_StandaloneCall()
    )

if __name__ == '__main__':
    main(sys.argv)
