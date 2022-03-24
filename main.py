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
        if not children:
            children = []
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
            elif isinstance(ctx, CypherParser.OC_ProjectionItemContext):
                expr = ctx.oC_Expression()
                variables.append((expr.getText(), expr.start))
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


def hasType(ctx, type_):
    found_merge = False
    def helper(ctx):
        nonlocal found_merge
        if isinstance(ctx, type_):
            found_merge = True
            return False
        return True

    visitor(ctx, helper)
    return found_merge


def addToScope(scope, variables):
    for var in variables:
        if var[0] not in scope:
            scope[var[0]] = []
        # TODO redefinition of variable should be an error!
        scope[var[0]].append(var[1])


def checkInScope(scope, variables):
    errors = 0
    for var in variables:
        if var[0] not in scope:
            l = var[1].line
            c = var[1].column
            log(f"UndefinedVariable: `{var[0]}`", l, c)
            errors += 1
    return errors


def handleReadCtx(scope, readCtx):
    if callCtx := readCtx.oC_InQueryCall():
        if yieldItemsCtx := callCtx.oC_YieldItems():
            # TODO handle YIELD *
            for yieldItemCtx in yieldItemsCtx.oC_YieldItem():
                ctx = yieldItemCtx.oC_Variable()
                scope[ctx.getText()] = [ctx.start]

    addToScope(scope, extractOutputVariables(readCtx))
    return 0


def handleUpdateCtx(scope, uctx):
    errors = 0
    if createctx := uctx.oC_Create():
        # TODO check for illegal redefinition
        addToScope(scope, extractOutputVariables(createctx))
    else:
        errors += checkInScope(scope, extractInputVariables(uctx))
    return errors


def handleWithOrReturnCtx(scope, withOrReturnCtx):
    return_vars = extractInputVariables(withOrReturnCtx)
    errors = checkInScope(scope, return_vars)

    # TODO handle with *
    for k in list(scope.keys()):
        del scope[k]
    addToScope(scope, extractOutputVariables(withOrReturnCtx))
    return errors


def processQuery(scope, queryCtx):
    errors = 0
    children = queryCtx.children
    for child in children:
        if isinstance(child, CypherParser.OC_ReadingClauseContext):
            errors += handleReadCtx(scope, child)
        elif isinstance(child, CypherParser.OC_UpdatingClauseContext):
            errors += handleUpdateCtx(scope, child)
        elif isinstance(child, CypherParser.OC_WithContext):
            errors += handleWithOrReturnCtx(scope, child)
        elif isinstance(child, CypherParser.OC_ReturnContext):
            errors += handleWithOrReturnCtx(scope, child)
        elif isinstance(child, CypherParser.OC_SinglePartQueryContext):
            errors += processQuery(scope, child)
    return errors


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
    assert not hasType(query, CypherParser.OC_MergeContext), (
        "Unsupported query - merge not implemented")
    assert not hasType(query, CypherParser.OC_UnionContext), (
        "Unsupported query - union not implemented")
    assert not hasType(query, CypherParser.OC_WhereContext), (
        "Unsupported query - where not implemented")

    if callquery := query.oC_StandaloneCall():
        if yield_items := callquery.oC_YieldItems():
            variables = []
            for yield_item in yield_items.oC_YieldItem():
                variables += extractVariables(yield_item)
        return

    regular_query = query.oC_RegularQuery()
    assert regular_query

    single_query = regular_query.oC_SingleQuery()

    scope = {}
    return processQuery(scope, single_query.children[0])

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
