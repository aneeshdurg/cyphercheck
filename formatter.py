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
            self.add_line(INDENT_STR + txt)
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

    def restore(self):
        state = self.save_ctx.pop()
        self.out_stream = self.out_stream[:state[0]]
        if len(self.out_stream) > 0:
            self.out_stream[-1] = self.out_stream[-1][:state[1]]

    def commit(self):
        self.save_ctx.pop()

    def format_OC_VariableContext(self, ctx):
        add_or_indent_add(ctx.getText())


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

    def format_OC_ExpressionContext(self, ctx, indent: str):
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
                        self.add_line(indent)
                        with self.indented():
                            self.format_OC_ExpressionContext(args[i], indent)
                    self.add_ignoring_limit(",")
        self.add_or_indent_add(")")



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
    visitor(getAST(
        "RETURN asdf(0, 1, 2, 3, "
        "'aaaaaaaaaa', 'bbbbbbbbbb', 'cccccccccc', 'dddddddddd', 'eeeeeeeeee',"
        "'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz')"), get_fn_call)
    assert fn_ctx is not None

    print(fn_ctx)

    formatter = Formatter()
    formatter.format_OC_FunctionInvocationContext(fn_ctx, INDENT_STR)
    print('\n'.join(formatter.out_stream))


if __name__ == "__main__":
    main()
