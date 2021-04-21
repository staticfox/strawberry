import strawberry
from strawberry.ast import ast_from_info
from strawberry.types import Info


EXPECTED_PYTHON_NAMES = [
    [
        "hello",
        [
            "ok",
            "object_b",
            [
                "fourth_field",
                "object_a",
                [
                    "second_field",
                    "third_field",
                ],
                "fifth_field",
            ],
            "python_names",
            "graphql_names",
        ],
    ]
]
EXPECTED_GRAPHQL_NAMES = [
    [
        "hello",
        [
            "ok",
            "objectB",
            [
                "fourthField",
                "objectA",
                [
                    "secondField",
                    "thirdField",
                ],
                "fifthField",
            ],
            "pythonNames",
            "graphqlNames",
        ],
    ]
]


def test_parse_ast():
    @strawberry.type
    class ObjectA:
        first_field: str
        second_field: int
        third_field: str

    @strawberry.type
    class ObjectB:
        fourth_field: bool
        object_a: ObjectA
        fifth_field: str

    @strawberry.type
    class Result:
        ok: bool
        object_b: ObjectB
        python_names: str
        graphql_names: str

    @strawberry.type
    class Query:
        @strawberry.field
        def hello(self, info: Info[str, str]) -> Result:
            ast = ast_from_info(info)

            assert ast.document_python_names == EXPECTED_PYTHON_NAMES
            assert ast.document_graphql_names == EXPECTED_GRAPHQL_NAMES

            return Result(
                ok=True,
                object_b=ObjectB(
                    fourth_field=True,
                    object_a=ObjectA(
                        first_field="a",
                        second_field=2,
                        third_field="c",
                    ),
                    fifth_field="d",
                ),
                python_names=str(ast.document_python_names),
                graphql_names=str(ast.document_graphql_names),
            )

    schema = strawberry.Schema(query=Query)

    query = """
        fragment AliasA on ObjectA {
            secondField
            thirdField
        }

        query {
            hello {
                ok
                objectB {
                    fourthField
                    objectA {
                        ... AliasA
                    }
                    fifthField
                }
                pythonNames
                graphqlNames
            }
        }"""

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data == {
        "hello": {
            "ok": True,
            "objectB": {
                "fourthField": True,
                "objectA": {
                    "secondField": 2,
                    "thirdField": "c",
                },
                "fifthField": "d",
            },
            "pythonNames": str(EXPECTED_PYTHON_NAMES),
            "graphqlNames": str(EXPECTED_GRAPHQL_NAMES),
        }
    }
