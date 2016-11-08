import importlib
import traceback
import sys
import types

# If you want the user modules to be reloaded each time the function is called, set this to True
PYTHON_MODULE_DEVELOPMENT = False

COROUTINES_DICT = {}
COROUTINES_COUNTER = 0

def format_error_string(stacktrace_str):
    """Return a formatted exception."""
    return '["e", "{}"]'.format(stacktrace_str.replace('"', '""'))

def format_response_string(return_value, sql_call=False, coroutine_id=None):
    """Return a formatted response.
    For now, it's just doing a dumb str() which may or may not work depending
    on the arguments passed. This should work as long as none of the arguments
    contain double quotes (").
    """

    if sql_call:
        return str(["s", coroutine_id, return_value])

    return str(["r", return_value])

def parse_input(input_value):
    """Parses the input value passed directly from the RVEngine.
    For now it just does an eval() which is INSECURE and HAS TO BE CHANGED!
    """

    return eval(input_value)


def handle_function_calling(function, args):
    global COROUTINES_DICT, COROUTINES_COUNTER

    if function == continue_coroutine:
        # Special handling
        return continue_coroutine(*args)

    # Call the requested function with the given arguments
    return_value = function(*args)

    if isinstance(return_value, types.CoroutineType):
        # This is a coroutine and has to be handled differently
        try:
            # Run the coroutine and get the yielded value
            yielded_value = return_value.send(None)

            COROUTINES_COUNTER += 1
            COROUTINES_DICT[COROUTINES_COUNTER] = return_value

            return format_response_string(yielded_value, True, COROUTINES_COUNTER)

        except StopIteration as iteration_exception:
            # The function has ended with a "return" statement
            return format_response_string(iteration_exception.value)

    else:
        return format_response_string(return_value)

# The extension entry point in python
def python_adapter(input_string):
    global FUNCTION_CACHE

    try:
        if input_string == "":
            return format_error_string("Input string cannot be empty")

        real_input = parse_input(input_string)
        full_function_name = real_input[0]
        function_args = real_input[1:]

        try:
            # Raise dummy exception if needs force-reload
            if PYTHON_MODULE_DEVELOPMENT:
                if not full_function_name.startswith('Pythia.'):
                    raise KeyError('Dummy KeyError')

            function = FUNCTION_CACHE[full_function_name]

        except KeyError:  # Function not cached, load the module
            function_path, function_name = full_function_name.rsplit('.', 1)

            try:
                module = sys.modules[function_path]

            except KeyError:
                # Module not imported yet, import it
                #print("Module not imported")
                module = importlib.import_module(function_path)

            # Force reloading the module if we're developing
            if PYTHON_MODULE_DEVELOPMENT:
                importlib.reload(module)

            # Get the requested function
            function = getattr(module, function_name)
            FUNCTION_CACHE[full_function_name] = function

        return handle_function_calling(function, function_args)

    except:
        return format_error_string(traceback.format_exc())

def continue_coroutine(_id, args):
    """Continue execution of a coroutine"""
    global COROUTINES_DICT, COROUTINES_COUNTER

    coroutine = COROUTINES_DICT.pop(_id)

    # Pass the value back to the coroutine and resume its execution
    try:
        next_request = coroutine.send(args)

        # Got next yield. Put the coroutine to the list again
        COROUTINES_DICT[_id] = coroutine
        return format_response_string(next_request, True, _id)

    except StopIteration as iteration_exception:
        # Function has ended with a return. Pass the value back
        return format_response_string(iteration_exception.value)

###############################################################################
# Below are testing functions which exist solely to check if everything is
# working correctly.
# If someone wants to check if their python module works, they should Call
# Pythia.test() and later Pythia.ping() to make sure they understand the syntax
###############################################################################

def test(*args):
    return "OK"

def ping(*args):
    return list(args)

FUNCTION_CACHE = {
    'Pythia.ping': ping,
    'Pythia.test': test,
    'Pythia.continue': continue_coroutine,
}

# Somehow Visual Studio cannot load this if there is a newline at The
# end of the file