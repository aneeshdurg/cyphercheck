echo -n "Total AST node types: "
grep "^oC" gen/Cypher.g4 | wc -l

echo -n "Supported AST node types: "
grep "def format_OC" formatter.py | wc -l
