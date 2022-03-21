import sys
from antlr4 import *
from gen.CypherLexer import CypherLexer
from gen.CypherParser import CypherParser


file_contents = []



def log(msg, l, c):
    print(f"{msg} on line: {l}, col: {c}", file=sys.stderr)
    print(f"{file_contents[l - 1].strip()}", file=sys.stderr)
    print(f"{' ' * c}^", file=sys.stderr)


def visitor(ctx, f):
    if not f(ctx):
        return
    try:
        children = ctx.children
    except AttributeError:
        children = []

    for c in children:
        visitor(c, f)


def extractVariables(ctx):
    variables = []
    def extractVariablesHelper(ctx):
        if isinstance(ctx, CypherParser.OC_VariableContext):
            variables.append((ctx.getText(), ctx.start))
            return False
        return True

    visitor(ctx, extractVariablesHelper)
    return variables


def extractOutputVariables(ctx):
    variables = []
    def extractVariablesHelper(ctx):
        outputting_clauses = (
            CypherParser.OC_ProjectionItemContext,
            CypherParser.OC_UnwindContext)
        if isinstance(ctx, outputting_clauses):
            if vctx := ctx.oC_Variable():
                for var in extractVariables(vctx):
                    variables.append(var)
            return False
        elif isinstance(ctx, CypherParser.OC_VariableContext):
            variables.append((ctx.getText(), ctx.start))
            return False
        return True
    visitor(ctx, extractVariablesHelper)
    return variables


def extractInputVariables(ctx):
    variables = []
    def extractVariablesHelper(ctx):
        if isinstance(ctx, CypherParser.OC_ProjectionItemContext):
            for var in extractVariables(ctx.oC_Expression()):
                variables.append(var)
            # We don't want the output of a projection
            return False
        if isinstance(ctx, CypherParser.OC_VariableContext):
            variables.append((ctx.getText(), ctx.start))
            return False
        return True

    visitor(ctx, extractVariablesHelper)
    return variables


def main(argv):
    global file_contents
    with open(argv[1]) as f:
        file_contents = f.readlines()

    input_stream = FileStream(argv[1])
    lexer = CypherLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CypherParser(stream)
    tree = parser.oC_Cypher()

    query = tree.oC_Statement().oC_Query()
    regular_query = query.oC_RegularQuery()
    assert regular_query, "Unsupported query"

    single_query = regular_query.oC_SingleQuery()
    assert single_query, "Unsupported query"

    errors = 0

    if (ctx := single_query.oC_SinglePartQuery()):
        reading_ctxs = ctx.oC_ReadingClause()
        scope = {}
        for rctx in reading_ctxs:
            for var in extractOutputVariables(rctx):
                if var[0] not in scope:
                    scope[var[0]] = []
                scope[var[0]].append(var[1])

        return_ctx = ctx.oC_Return()
        return_vars = extractInputVariables(return_ctx)
        for var in return_vars:
            if var[0] not in scope:
                l = var[1].line
                c = var[1].column
                log(f"Unknown variable `{var[0]}`", l, c)
                errors += 1
    else:
        raise Exception("Unsupported query")

    return errors

if __name__ == '__main__':
    sys.exit(main(sys.argv))
