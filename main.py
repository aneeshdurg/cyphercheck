#!/usr/bin/python3
import argparse
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


def hasMerge(ctx):
    found_merge = False
    def helper(ctx):
        nonlocal found_merge
        if isinstance(ctx, CypherParser.OC_MergeContext):
            found_merge = True
            return False
        return True

    visitor(ctx, helper)
    return found_merge


def main(argv):
    global file_contents

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="store")
    parser.add_argument("--file", action="store")

    args = parser.parse_args(argv)

    input_stream = None
    if args.query:
        file_contents = args.query.split("\n")
        input_stream = InputStream(args.query)
    elif args.file:
        with open(args.file) as f:
            file_contents = f.readlines()
        input_stream = FileStream(args.file)
    else:
        assert False

    lexer = CypherLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CypherParser(stream)
    tree = parser.oC_Cypher()

    query = tree.oC_Statement().oC_Query()

    assert not hasMerge(query), "Unsupported query - merge not implemented"

    regular_query = query.oC_RegularQuery()
    assert regular_query, "Unsupported query"

    single_query = regular_query.oC_SingleQuery()
    assert single_query, "Unsupported query"

    errors = 0

    if (ctx := single_query.oC_SinglePartQuery()):
        reading_ctxs = ctx.oC_ReadingClause()
        scope = {}

        def checkInScope(variables):
            nonlocal scope
            nonlocal errors
            for var in variables:
                if var[0] not in scope:
                    l = var[1].line
                    c = var[1].column
                    log(f"UndefinedVariable: `{var[0]}`", l, c)
                    errors += 1

        def addToScope(variables):
            nonlocal scope
            for var in variables:
                if var[0] not in scope:
                    scope[var[0]] = []
                scope[var[0]].append(var[1])

        for rctx in reading_ctxs:
            addToScope(extractOutputVariables(rctx))

        updating_ctxs = ctx.oC_UpdatingClause()
        for uctx in updating_ctxs:
            if createctx := uctx.oC_Create():
                # TODO check for illegal redefinition
                addToScope(extractOutputVariables(createctx))
            else:
                checkInScope(extractInputVariables(uctx))

        if return_ctx := ctx.oC_Return():
            return_vars = extractInputVariables(return_ctx)
            checkInScope(return_vars)
    else:
        raise Exception("Unsupported query")

    return errors

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
