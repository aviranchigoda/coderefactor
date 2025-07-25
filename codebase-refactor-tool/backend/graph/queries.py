"""
Cypher query templates for Neo4j graph operations.
"""

# Node Creation Queries
CREATE_FILE_NODE = """
CREATE (f:File {
    path: $path,
    name: $name,
    extension: $extension,
    size: $size
})
RETURN f
"""

CREATE_CLASS_NODE = """
CREATE (c:Class {
    name: $name,
    line_start: $line_start,
    line_end: $line_end
})
RETURN c
"""

CREATE_METHOD_NODE = """
CREATE (m:Method {
    name: $name,
    parameters: $parameters,
    return_type: $return_type,
    line_start: $line_start,
    line_end: $line_end
})
RETURN m
"""

CREATE_FUNCTION_NODE = """
CREATE (f:Function {
    name: $name,
    parameters: $parameters,
    return_type: $return_type,
    line_start: $line_start,
    line_end: $line_end
})
RETURN f
"""

CREATE_LINT_ERROR_NODE = """
CREATE (e:LintError {
    type: $type,
    message: $message,
    severity: $severity,
    line: $line
})
RETURN e
"""

# Relationship Creation Queries
CREATE_FILE_CONTAINS_CLASS = """
MATCH (f:File {path: $file_path})
MATCH (c:Class {name: $class_name, line_start: $line_start})
CREATE (f)-[:CONTAINS]->(c)
"""

CREATE_CLASS_HAS_METHOD = """
MATCH (c:Class {name: $class_name, line_start: $class_line_start})
MATCH (m:Method {name: $method_name, line_start: $method_line_start})
CREATE (c)-[:HAS_METHOD]->(m)
"""

CREATE_FILE_CONTAINS_FUNCTION = """
MATCH (f:File {path: $file_path})
MATCH (fn:Function {name: $function_name, line_start: $line_start})
CREATE (f)-[:CONTAINS]->(fn)
"""

CREATE_METHOD_CALLS_METHOD = """
MATCH (caller:Method {name: $caller_name, line_start: $caller_line_start})
MATCH (callee:Method {name: $callee_name, line_start: $callee_line_start})
CREATE (caller)-[:CALLS]->(callee)
"""

CREATE_METHOD_CALLS_FUNCTION = """
MATCH (caller:Method {name: $caller_name, line_start: $caller_line_start})
MATCH (callee:Function {name: $callee_name, line_start: $callee_line_start})
CREATE (caller)-[:CALLS]->(callee)
"""

CREATE_FUNCTION_CALLS_METHOD = """
MATCH (caller:Function {name: $caller_name, line_start: $caller_line_start})
MATCH (callee:Method {name: $callee_name, line_start: $callee_line_start})
CREATE (caller)-[:CALLS]->(callee)
"""

CREATE_FUNCTION_CALLS_FUNCTION = """
MATCH (caller:Function {name: $caller_name, line_start: $caller_line_start})
MATCH (callee:Function {name: $callee_name, line_start: $callee_line_start})
CREATE (caller)-[:CALLS]->(callee)
"""

CREATE_METHOD_HAS_ERROR = """
MATCH (m:Method {name: $method_name, line_start: $method_line_start})
MATCH (e:LintError {line: $error_line, type: $error_type, message: $error_message})
CREATE (m)-[:HAS_ERROR]->(e)
"""

CREATE_FUNCTION_HAS_ERROR = """
MATCH (f:Function {name: $function_name, line_start: $function_line_start})
MATCH (e:LintError {line: $error_line, type: $error_type, message: $error_message})
CREATE (f)-[:HAS_ERROR]->(e)
"""

# Combined Creation Queries (for efficiency)
CREATE_FILE_WITH_CLASS = """
CREATE (f:File {
    path: $file_path,
    name: $file_name,
    extension: $file_extension,
    size: $file_size
})
CREATE (c:Class {
    name: $class_name,
    line_start: $class_line_start,
    line_end: $class_line_end
})
CREATE (f)-[:CONTAINS]->(c)
RETURN f, c
"""

CREATE_CLASS_WITH_METHOD = """
MATCH (c:Class {name: $class_name, line_start: $class_line_start})
CREATE (m:Method {
    name: $method_name,
    parameters: $method_parameters,
    return_type: $method_return_type,
    line_start: $method_line_start,
    line_end: $method_line_end
})
CREATE (c)-[:HAS_METHOD]->(m)
RETURN c, m
"""

# Query Queries
FIND_FILE_BY_PATH = """
MATCH (f:File {path: $path})
RETURN f
"""

FIND_CLASS_BY_NAME_AND_FILE = """
MATCH (f:File {path: $file_path})-[:CONTAINS]->(c:Class {name: $class_name})
RETURN c
"""

FIND_METHOD_BY_NAME_AND_CLASS = """
MATCH (c:Class {name: $class_name})-[:HAS_METHOD]->(m:Method {name: $method_name})
RETURN m
"""

FIND_FUNCTION_BY_NAME_AND_FILE = """
MATCH (f:File {path: $file_path})-[:CONTAINS]->(fn:Function {name: $function_name})
RETURN fn
"""

FIND_ALL_CALLS_FROM_METHOD = """
MATCH (m:Method {name: $method_name, line_start: $line_start})-[:CALLS]->(target)
RETURN target
"""

FIND_ALL_CALLS_FROM_FUNCTION = """
MATCH (f:Function {name: $function_name, line_start: $line_start})-[:CALLS]->(target)
RETURN target
"""

FIND_ERRORS_FOR_METHOD = """
MATCH (m:Method {name: $method_name, line_start: $line_start})-[:HAS_ERROR]->(e:LintError)
RETURN e
"""

FIND_ERRORS_FOR_FUNCTION = """
MATCH (f:Function {name: $function_name, line_start: $line_start})-[:HAS_ERROR]->(e:LintError)
RETURN e
"""

# Cleanup Queries
DELETE_ALL_NODES = """
MATCH (n)
DETACH DELETE n
"""

DELETE_FILE_AND_CONTENTS = """
MATCH (f:File {path: $file_path})
OPTIONAL MATCH (f)-[:CONTAINS*]->(content)
DETACH DELETE f, content
"""

# Analysis Queries
GET_FILE_STRUCTURE = """
MATCH (f:File {path: $file_path})
OPTIONAL MATCH (f)-[:CONTAINS]->(c:Class)
OPTIONAL MATCH (c)-[:HAS_METHOD]->(m:Method)
OPTIONAL MATCH (f)-[:CONTAINS]->(fn:Function)
RETURN f, collect(DISTINCT c) as classes, collect(DISTINCT m) as methods, collect(DISTINCT fn) as functions
"""

GET_CALL_GRAPH = """
MATCH (caller)-[:CALLS]->(callee)
WHERE caller:Method OR caller:Function
RETURN caller, callee
"""

GET_ERROR_SUMMARY = """
MATCH (entity)-[:HAS_ERROR]->(e:LintError)
WHERE entity:Method OR entity:Function
RETURN entity, collect(e) as errors
"""