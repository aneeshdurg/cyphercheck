#!/usr/bin/python3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Tuple

from antlr4 import *

from gen.CypherLexer import CypherLexer
from gen.CypherParser import CypherParser

from visitor import *

MAX_LINE_LENGTH = 80
INDENT_STR = "  "


class Formatter:
    out_stream: List[str]
    save_ctx: List[Tuple[int, int]]
    indent: str

    def __init__(self):
        self.out_stream = []
        self.save_ctx = []
        self.indent = ""

    def last_line_length(self) -> int:
        if len(self.out_stream) == 0:
            return 0
        return len(self.out_stream[-1])


    def add_to_last_line(self, txt: str):
        if len(self.out_stream) > 0:
            self.out_stream[-1] += txt
        else:
            self.out_stream = [txt]


    def add_line(self, txt: str):
        self.out_stream += [txt]


    def add_or_indent_add(self, txt: str):
        if (len(txt) + self.last_line_length()) >= 80:
            self.add_line(self.indent + txt)
        else:
            self.add_to_last_line(txt)

    def add_ignoring_limit(self, txt: str):
        if len(self.out_stream) > 0:
            self.out_stream[-1] += txt
        else:
            self.add_line(txt)

    def save(self):
        state = (len(self.out_stream), self.last_line_length())
        self.save_ctx.append(state)

    def lines_increased(self):
        state = (len(self.out_stream), self.last_line_length())
        return state[0] != self.save_ctx[-1][0]

    def restore(self):
        state = self.save_ctx.pop()
        self.out_stream = self.out_stream[:state[0]]
        if len(self.out_stream) > 0:
            self.out_stream[-1] = self.out_stream[-1][:state[1]]

    def commit(self):
        self.save_ctx.pop()

    def get_formatted_function_args(self, needs_space, needs_comma, ctx):
        if needs_space:
            self.add_ignoring_limit(" ")

    @contextmanager
    def indented(self):
        try:
            self.indent += INDENT_STR
            yield
        finally:
            self.indent = self.indent[:-len(INDENT_STR)]

    def format_OC_VariableContext(self, ctx):
        self.add_or_indent_add(ctx.getText())

    def format_OC_LiteralContext(self, ctx):
        if isinstance(ctx, CypherParser.OC_MapLiteralContext):
            pass
        elif isinstance(ctx, CypherParser.OC_ListLiteralContext):
            pass
        else:
            self.add_or_indent_add(ctx.getText())

    def format_OC_FunctionInvocationContext(self, ctx, indent: str):
        start_call = ctx.oC_FunctionName().getText() + '('

        is_distinct = False
        def find_distinct(ctx):
            nonlocal is_distinct
            if isinstance(ctx, tree.Tree.TerminalNodeImpl):
                if ctx.getText().lower == "distinct":
                    is_distinct = True
                return False
            return True
        visitor.visitor(ctx, find_distinct)

        self.add_or_indent_add(start_call)

        with self.indented():
            if is_distinct:
                self.add_or_indent_add("DISTINCT")

            # TODO provide options for different ways of formatting args
            args = ctx.oC_Expression()
            for i in range(len(args)):
                if (i == 0 and is_distinct) or i > 0:
                    self.add_ignoring_limit(" ")
                self.save()
                self.format_OC_ExpressionContext(args[i], indent)
                is_last = i == (len(args) - 1)
                if not is_last:
                    if len(self.out_stream[-1]) >= MAX_LINE_LENGTH:
                        self.restore()
                        self.add_line(self.indent)
                        with self.indented():
                            self.format_OC_ExpressionContext(args[i], indent)
                    else:
                        self.commit()
                    self.add_ignoring_limit(",")
        self.add_or_indent_add(")")

    def format_OC_NotExpressionContext(ctx):
        not_count = 0
        def count_nots(ctx):
            nonlocal not_count
            if isinstance(ctx, tree.Tree.TerminalNodeImpl):
                if ctx.getText().lower == "not":
                    not_count += 1
                return False
            return True
        visitor(ctx, count_nots)
        if (count_nots % 2) == 1:
            self.save()
            self.add_ignoring_limit(" NOT ")
            if self.last_line_length() >= MAX_LINE_LENGTH:
                self.restore()
                self.add_line(self.indent)
                self.add_or_indent_add("NOT ")


    def format_OC_AndExpressionContext(ctx):
        self.format_OC_BinExpressionContext(
            ctx,
            lambda x: x.oC_NotExpression(),
            self.format_OC_NotExpressionContext,
            "AND")

    def format_OC_XOrExpressionContext(ctx):
        self.format_OC_BinExpressionContext(
            ctx,
            lambda x: x.oC_AndExpression(),
            self.format_OC_AndExpressionContext,
            "XOR")

    def format_OC_OrExpressionContext(ctx):
        self.format_OC_BinExpressionContext(
            ctx,
            lambda x: x.oC_XOrExpression(),
            self.format_OC_XOrExpressionContext,
            "OR")

    def format_OC_BinExpressionContext(ctx, get_next, formatter, op: str):
        parts = get_next(ctx)
        lhs = parts[0]
        formatter(lhs)
        if len(parts) > 1:
            self.save()
            self.add_ignoring_limit(f" {op} ")
            if self.last_line_length() >= MAX_LINE_LENGTH:
                self.restore()
                self.add_line(self.indent)
                self.add_or_indent_add(f"{op} ")
            formatter(parts[1])


    def format_OC_ExpressionContext(self, ctx):
        self.format_OC_OrExpressionContext(ctx.oC_OrExpression())

    def format_OC_ProjectionItemContext(self, ctx):
        self.format_OC_ExpressionContext(ctx.oC_Expression())

        var = ctx.oC_Variable()
        if var:
            self.save()
            self.add_ignoring_limit(" AS ")
            if self.last_line_length() >= MAX_LINE_LENGTH:
                self.restore()
                self.add_line(self.indent)
                self.add_or_indent_add("AS ")
            self.format_OC_VariableContext(var)

    def format_OC_ProjectionItemsContext(self, ctx):
        # TODO handle *
        items = ctx.oC_ProjectionItem()
        for i in range(len(items)):
            self.save()
            self.format_OC_ProjectionItemContext(items[i])
            if i != (len(items) - 1):
                self.add_ignoring_limit(",")
                if len(self.out_stream[-1]) >= MAX_LINE_LENGTH:
                    self.restore()
                    self.add_line(self.indent)
                    with self.indented():
                        self.format_OC_ProjectionItemContext(items[i])
                        self.add_ignoring_limit(",")

    def format_OC_ProjectionBodyContext(self, ctx):
        # TODO check for DISTINCT
        is_distinct = False
        def find_distinct(ctx):
            nonlocal is_distinct
            if isinstance(ctx, tree.Tree.TerminalNodeImpl):
                if ctx.getText().lower == "distinct":
                    is_distinct = True
                return False
            return True
        visitor(ctx, find_distinct)

        self.format_OC_ProjectionItemsContext(ctx.oC_ProjectionItems())

        if is_distinct:
            self.add_or_indent_add("DISTINCT ")

        # TODO handle order, skip, limit

    def format_OC_ReturnContext(self, ctx, retry=False):
        if self.last_line_length() and not retry:
            self.save()

        self.add_or_indent_add("RETURN ")
        self.format_OC_ProjectionBodyContext(ctx.oC_ProjectionBody())

        if self.last_line_length() and not retry:
            if self.lines_increased():
                self.restore()
                self.add_line(self.indent)
                with self.indented():
                    self.format_OC_ReturnContext(ctx, retry=True)

    def format_OC_SinglePartQueryContext(self, ctx):
        assert not ctx.oC_ReadingClause()
        assert not ctx.oC_UpdatingClause()

        ret = ctx.oC_Return()
        assert ret
        self.format_OC_ReturnContext(ret)


    def format_OC_SingleQueryContext(self, ctx):
        assert not ctx.oC_MultiPartQuery()
        query = ctx.oC_SinglePartQuery()
        self.format_OC_SinglePartQueryContext(query)


    def format_OC_RegularQueryContext(self, ctx):
        query = ctx.oC_SingleQuery()
        assert not ctx.oC_Union()
        self.format_OC_SingleQueryContext(query)

    def format_OC_QueryContext(self, ctx):
        query = ctx.oC_RegularQuery()
        assert query
        self.format_OC_RegularQueryContext(query)

    def format_OC_StatementContext(self, ctx):
        self.format_OC_QueryContext(ctx.oC_Query())

    def format_OC_CypherContext(self, ctx):
        stmt = ctx.oC_Statement()
        self.format_OC_StatementContext(stmt)


def main():
    from main import getAST
    from visitor import visitor

    fn_ctx = None
    def get_fn_call(ctx):
        nonlocal fn_ctx
        if isinstance(ctx, CypherParser.OC_FunctionInvocationContext):
            fn_ctx = ctx
            return False
        return True
    ast = getAST(
        "RETURN asdf(0, 1, 2, 3, "
        "'aaaaaaaaaa', 'bbbbbbbbbb', 'cccccccccc', 'dddddddddd', 'eeeeeeeeee', 'ffffffffff', "
        "'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz')")

    # visitor(ast, get_fn_call)
    # assert fn_ctx is not None

    # print(fn_ctx)

    formatter = Formatter()
    # formatter.format_OC_FunctionInvocationContext(fn_ctx, INDENT_STR)
    formatter.format_OC_CypherContext(ast)
    print('\n'.join(formatter.out_stream))


if __name__ == "__main__":
    main()
