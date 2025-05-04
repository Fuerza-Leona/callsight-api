
# Unit Testing

The following document summarizes technical concepts fundamental to the testing approach taken to ensure the quality of the Callsight API codebase. Testing was implemented with the `pytest` and `unittest` modules to ensure compliance with best practices in Python development.

First, let's understand the technical concepts surrounding testing.

## Mocking

[Mocking with `unittest` documentation](https://docs.python.org/3/library/unittest.mock.html#quick-guide)

The explanations below use as reference the `test_store_conversation_data` unit test located inside the `test_storage_service.py` testing script.

**`MagicMock` and `AsyncMock`**

Creates mock classes we can add methods to. Why is this important? In one word: isolation. Say we are testing a `store(data, db_client)` function. To test it we would create a `test_store()` test. However, we won't use the real database client, because we want to isolate our test from external dependencies (other functions). Instead, we create a mock database client. This mock will have the same functions called inside `store()`, but with our nominal, successful, expected `return_value`.

**`patch`**

Functions we test often depend on other functions that we aren't directly passing to them. For example, `store()` might use a `helper()` defined in the same script (context) it's located. So, how do we mock `helper()` too? We have to modify the "context" in which we are through a `with patch(helper) as mocked_helper:` block. Every call to `helper()` inside that `with` block, inside that context, will call `mocked_helper` instead of the original function. It's like decorating the original function through a mocked interface.

**`return_value` vs `side_effect`**

When we define a mock, we must give it a return value in one way or another, since that value will be used as our tested function is executing. The straightforward way is `mock.called_method.return_value = something`. The advanced, more dynamic way of doing it is through side effects. A `side_effect` can be a function or an iterable, or an iterable of functions. Either way, we'll call the side effects with the inputs that the mock was called with. The result of the each function is used as return value for the mock.

Examples with concepts above

```python
from unittest.mock import MagicMock, AsyncMock, patch

# Simple return_value
mock1 = MagicMock()
mock1.return_value = "fixed value"
print(mock1())  # Output: fixed value
print(mock1())  # Output: fixed value

# side_effect with a function
def my_side_effect(arg1, arg2):
    return f"arg1: {arg1}, arg2: {arg2}"

mock2 = MagicMock()
mock2.side_effect = my_side_effect
print(mock2("hello", "world"))  # Output: arg1: hello, arg2: world
print(mock2(1, 2))  # Output: arg1: 1, arg2: 2

mock3 = MagicMock()
mock3.table.return_value.insert.side_effect = [
    topic_insert_mock1,  # First call - for topic 1
    junction_insert_mock1,  # Second call - for junction table with topic
]

# Example using patch and AsyncMock
async def my_async_function(db_client):
    result1 = await db_client.get_data()
    result2 = await db_client.process_data(result1)
    return result2

async def test_my_async_function():
    with (
	    patch("__main__.my_async_function") as mock_get_data,
	    patch("__main__.my_async_function") as mock_process_data,
    ):
        mock_get_data.return_value = AsyncMock()
        mock_process_data.return_value = AsyncMock()
        mock_get_data.return_value.return_value = "some data"
        mock_process_data.return_value.return_value = "processed data"

        result = await my_async_function(MagicMock())
        assert result == "processed data"
```

