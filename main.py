#!/usr/bin/python3
import argparse
import sys

from dataclasses import dataclass
from typing import Dict, List

from antlr4 import *

from gen.CypherLexer import CypherLexer
from gen.CypherParser import CypherParser

from visitor import *


file_contents = []


def log(msg, l, c):
    print(f"{msg} on line: {l}, col: {c}", file=sys.stderr)
    print(f"{file_contents[l - 1].strip()}", file=sys.stderr)
    print(f"{' ' * c}^", file=sys.stderr)


@dataclass
class Variable:
    ctx: ParserRuleContext

    @property
    def name(self):
        return self.ctx.getText()

    @property
    def line(self):
        return self.ctx.start.line

    @property
    def col(self):
        return self.ctx.start.column


class Scope:
    variables: Dict[str, Variable]

    def __init__(self):
        self.variables = {}

    def add(self, variables: List[Variable]):
        for var in variables:
            if var.name in self.variables:
                return
            self.variables[var.name] = var

    def checkInScope(self, ctxs: List[Variable]) -> None:
        missing = 0
        for ctx in ctxs:
            if ctx.name not in self.variables:
                log("UndefinedVariable", ctx.line, ctx.col)
                missing += 1
        return missing

    def clear(self):
        self.variables = {}

    def checkCtxForUndefinedVariables(self, ctx) -> List[Variable]:
        undefined_vars = []
        def visit(ctx):
            nonlocal undefined_vars

            if isinstance(ctx, CypherParser.OC_ExpressionContext):
                # if this expression was a variable because of a projection,
                # then stop here
                if ctx.getText() in self.variables:
                    return False
                # recursively search this expression and find all atoms
            elif isinstance(ctx, CypherParser.OC_AtomContext):
                if vctx := ctx.oC_Variable():
                    if vctx.getText() not in self.variables:
                        undefined_vars.append(Variable(vctx))
                        return False
            return True

        visitor(ctx, visit)
        return undefined_vars

    def debug(self, tag):
        print(f"scope: {tag}")
        for var in self.variables:
            ctx = self.variables[var]
            print("  {}: {},{}".format(var, ctx.line, ctx.col))


def extractDefinedVariables(ctx):
    """Extract variables that were defined in this context."""
    variables = []

    def visit(ctx):
        # These are all clauses that can define variables
        defining_clauses = (
            CypherParser.OC_ProjectionItemContext,
            CypherParser.OC_UnwindContext,
            CypherParser.OC_YieldItemContext,
            CypherParser.OC_NodePatternContext,
            CypherParser.OC_RelationshipDetailContext,
        )
        if isinstance(ctx, defining_clauses):
            if vctx := ctx.oC_Variable():
                variables.append(Variable(vctx))
            elif isinstance(ctx, CypherParser.OC_ProjectionItemContext):
                # If a projection is just an expression with no "AS" that
                # expression gets propogated as a column name
                expr = ctx.oC_Expression()
                variables.append(Variable(expr))
            return False
        return True

    visitor(ctx, visit)
    return variables


def logUndefinedVariables(ctx):
    variables = []

    def visit(ctx):
        if isinstance(ctx, CypherParser.OC_AtomContext):
            if vctx := ctx.oC_Variable():
                variables.append(Variable(vctx))
                return False
        return True

    visitor(ctx, visit)
    return variables


def handleCtx(scope, ctx):
    undefined_vars = scope.checkCtxForUndefinedVariables(ctx)
    for var in undefined_vars:
        log("UndefinedVariable", var.line, var.col)
    scope.add(extractDefinedVariables(ctx))
    return len(undefined_vars)


def handleUpdateCtx(scope, uctx):
    scope.add(extractDefinedVariables(uctx))
    undefined_vars = scope.checkCtxForUndefinedVariables(uctx)
    for var in undefined_vars:
        log("UndefinedVariable", var.line, var.col)
    return len(undefined_vars)


def processQuery(scope: Scope, queryCtx) -> int:
    errors = 0
    children = queryCtx.children
    for child in children:
        if isinstance(child, CypherParser.OC_ReadingClauseContext):
            errors += handleCtx(scope, child)
        elif isinstance(child, CypherParser.OC_UpdatingClauseContext):
            errors += handleUpdateCtx(scope, child)
        elif isinstance(child, CypherParser.OC_WithContext):
            errors += handleCtx(scope, child)
        elif isinstance(child, CypherParser.OC_ReturnContext):
            errors += handleCtx(scope, child)
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
    assert not hasType(
        query, CypherParser.OC_MergeContext
    ), "Unsupported query - merge not implemented"
    assert not hasType(
        query, CypherParser.OC_UnionContext
    ), "Unsupported query - union not implemented"
    assert not hasType(
        query, CypherParser.OC_WhereContext
    ), "Unsupported query - where not implemented"

    if callquery := query.oC_StandaloneCall():
        if yield_items := callquery.oC_YieldItems():
            for yield_item in yield_items.oC_YieldItem():
                # TODO ???
                pass
        return

    regular_query = query.oC_RegularQuery()
    assert regular_query

    single_query = regular_query.oC_SingleQuery()

    scope = Scope()
    return processQuery(scope, single_query.children[0])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
