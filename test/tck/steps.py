from behave import given, when, then, step


@given('an empty graph')
@given('any graph')
@given('the binary-tree-1 graph')
@given('the binary-tree-2 graph')
@given('after having executed')
@given('having executed')
@then('having executed')
@given('there exists a procedure {proc}')
def step_impl(context, **kwargs):
    pass


@given('parameter values are')
def params_wrapper_1(context):
    pass


@given('parameters are')
def params_wrapper_2(context):
    pass


@when('executing control query')
def execute_control_query(context):
    pass

@then('the result should be empty')
@then('the result should be (ignoring element order for lists)')
@then('the result should be, in any order')
@then('the result should be, in order')
@then('the side effects should be')
@then('no side effects')
def step_impl(context):
    pass


@then('a {errorType} should be raised at runtime: {error}')
def runtime_errors(context, errorType, error):
    pass


@then('{errorType} should be raised at runtime: {error}')
def runtime_errors(context, errorType, error):
    pass


@when('executing query')
def executing_query(context):
    pass


@then('a SyntaxError should be raised at compile time: {error}')
def syntax_error(context, error):
    # assert False
    pass


@then('{errorType} should be raised at compile time: {error}')
def generic_compile_time_error(context, errorType, error):
    pass


@then('{errorType} should be raised at any time: {error}')
def any_time_error(context, errorType, error):
    pass
