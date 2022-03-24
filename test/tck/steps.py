import os
import subprocess

from behave import given, when, then, step


@given('an empty graph')
@given('any graph')
@given('the binary-tree-1 graph')
@given('the binary-tree-2 graph')
@given('after having executed')
@given('there exists a procedure {proc}')
def step_impl(context, **kwargs):
    pass


@given('having executed')
@then('having executed')
@when('executing control query')
@when('executing query')
def executing_query(context):
    exe_path = os.environ['CYPHERCHECK']
    cmd = [exe_path, '--query', context.text]
    context.proc = subprocess.Popen(
        cmd, stderr=subprocess.PIPE)


@given('parameter values are')
def params_wrapper_1(context):
    pass


@given('parameters are')
def params_wrapper_2(context):
    pass


@then('a SyntaxError should be raised at compile time: {error}')
def syntax_error(context, error):
    if error != 'UndefinedVariable':
        return
    context.proc.wait()
    stderr = context.proc.stderr.read().decode()
    if 'Unsupported query' in stderr:
        raise Exception('Unsupported query {}'.format(stderr))
    assert 'UndefinedVariable' in stderr
    assert context.proc.returncode != 0


@then('the result should be empty')
@then('the result should be (ignoring element order for lists)')
@then('the result should be, in any order')
@then('the result should be, in order')
@then('the side effects should be')
@then('no side effects')
@then('{errorType} should be raised at runtime: {error}')
@then('{errorType} should be raised at any time: {error}')
@then('{errorType} should be raised at compile time: {error}')
def step_impl(context, **kwargs):
    context.proc.wait()
    stderr = context.proc.stderr.read().decode()
    if 'Unsupported query' in stderr:
        raise Exception('Unsupported query {}'.format(stderr))
    assert not stderr
