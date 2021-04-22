import dataclasses
from typing import Any, Dict, List, Union

from graphql.language.ast import (
    FieldNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    SelectionNode,
)
from graphql.pyutils.convert_case import camel_to_snake

from strawberry.types.info import Info


@dataclasses.dataclass
class Node:
    """
    Describes a field embedded within the document.
    """

    python_name: str
    graphql_name: str

    def __repr__(self) -> str:
        return self.python_name


Document = List[List[Node]]
LabelMap = List[List[str]]


@dataclasses.dataclass
class ASTFromInfo:
    """
    Describes a simplified version of the document's AST.
    """

    fragments: Dict[str, Document]
    document: Document

    # TODO: cached property?
    @property
    def document_python_names(self) -> LabelMap:
        return recurisve_extract(self.document, "python_name")

    @property
    def document_graphql_names(self) -> LabelMap:
        return recurisve_extract(self.document, "graphql_name")


def ast_from_info(info: Info) -> ASTFromInfo:
    """
    Returns a list of Node instances that represent the document embedded in info.

    The ast object contains 2 fields, fragments and document.

    The fragments field is a map of fragment names and their corresponding
    Document instance. Inline fragments are not tracked and are directly
    embedded in to the document.

    The document field contains an ordered list of Node instances which
    corresponds to the document itself. Note that all fragments are
    already expanded.

    The ast object also provides 2 convenience methods for resolving
    the document as a collection of strings instead of Node instances.

    Example usages:

    >>> ast = ast_from_info(info)
    >>> print(ast.document_python_names)
    ... [["get_viewer", ["ok", "viewer", ["name", "is_active"]]] ...
    >>> print(ast.document_graphql_names)
    ... [["getViewer", ["ok", "viewer", ["name", "isActive"]]] ...
    """
    builder = ASTBuilder(info)
    return builder.result


class ASTBuilder:
    """
    Resolves a document embedded within an Info instance.

    Under normal usage, this class is only meant to return
    an instance of ASTFromInfo from the result property.

    Direct usage is available and subclassing is encouraged
    if you need to modify the document or fragments' build
    process.
    """

    def __init__(self, info: Info):
        self.info = info
        self.fragments: Dict[str, Document] = {}
        self.document: Document = []

        self.load_fragments()
        self.load_document()

    def load_fragments(self):
        for key, fragment in self.info.fragments.items():
            self.fragments[key] = self.parse_leaf_node(
                fragment.selection_set.selections
            )

    def load_document(self):
        self.document = self.parse_leaf_node(self.info.field_nodes)

    def parse_leaf_node(
        self, node: Union[FieldNode, List[FieldNode], FragmentSpreadNode, SelectionNode]
    ) -> Any:
        # TODO: don't know how to annotate this return type.
        nodes = []

        if isinstance(node, List):
            for inner_node in node:
                nodes.append(self.parse_leaf_node(inner_node))
            return nodes

        if node.kind == "inline_fragment" and isinstance(node, InlineFragmentNode):
            return self.parse_inline_fragment(node)

        if node.kind == "fragment_definition" and isinstance(node, FieldNode):
            return self.parse_fragment_definition(node)

        if node.kind == "fragment_spread" and isinstance(node, FragmentSpreadNode):
            return self.parse_fragment_spread(node)

        if node.kind == "field" and isinstance(node, FieldNode):
            return self.parse_field(node)

        # what do?
        return []

    def parse_inline_fragment(self, node: FieldNode) -> List[List[Node]]:
        if not node.selection_set:
            return []

        return [
            self.parse_leaf_node(selection)
            for selection in node.selection_set.selections
        ]

    def parse_fragment_definition(self, node: FieldNode) -> List[List[Node]]:
        if not node.selection_set:
            return []

        return [
            self.parse_leaf_node(selection)
            for selection in node.selection_set.selections
        ]

    def parse_fragment_spread(self, node: FragmentSpreadNode) -> List[List[Node]]:
        return self.fragments[node.name.value]

    def parse_field(self, node: FieldNode) -> Any:
        # TODO: don't know how to annotate this return type.
        this_node = Node(
            python_name=camel_to_snake(node.name.value),
            graphql_name=node.name.value,
        )

        # This is a true leaf.
        if not node.selection_set:
            return this_node

        # This leaf also has leaves, start the cycle again.
        nodes: List[Document] = []

        for selection in node.selection_set.selections:
            result = self.parse_leaf_node(selection)

            if selection.kind == "fragment_spread":
                # This is the expanded fragment that we pre-calculated from earlier.
                nodes = result
            elif isinstance(result, List):
                # The result of a leaf that also had leaves.
                nodes.extend(result)
            else:
                # Single leaf.
                nodes.append(result)

        return [this_node, nodes]

    @property
    def result(self) -> ASTFromInfo:
        return ASTFromInfo(
            fragments=self.fragments,
            document=self.document,
        )


# Helper to be used for the ASTFromInfo convenience properties.
def recurisve_extract(
    nodes: List[Any], attr: str, node_map: List[Any] = None
) -> LabelMap:
    # TODO: don't know how recursively annotate the arguments.
    if node_map is None:
        node_map = []

    for node in nodes:
        if isinstance(node, list):
            node_map.append(recurisve_extract(node, attr))
        else:
            node_map.append(getattr(node, attr))
    return node_map
