import collections

from aiomotorengine.query.base import QueryOperator
from aiomotorengine.query.exists import ExistsQueryOperator
from aiomotorengine.query.greater_than import GreaterThanQueryOperator
from aiomotorengine.query.greater_than_or_equal import GreaterThanOrEqualQueryOperator
from aiomotorengine.query.lesser_than import LesserThanQueryOperator
from aiomotorengine.query.lesser_than_or_equal import LesserThanOrEqualQueryOperator
from aiomotorengine.query.in_operator import InQueryOperator
from aiomotorengine.query.is_null import IsNullQueryOperator
from aiomotorengine.query.not_operator import NotOperator
from aiomotorengine.query.not_equal import NotEqualQueryOperator


OPERATORS = {
    'exists': ExistsQueryOperator,
    'gt': GreaterThanQueryOperator,
    'gte': GreaterThanOrEqualQueryOperator,
    'lt': LesserThanQueryOperator,
    'lte': LesserThanOrEqualQueryOperator,
    'in': InQueryOperator,
    'is_null': IsNullQueryOperator,
    'ne': NotEqualQueryOperator,
    'not': NotOperator,
}


class DefaultOperator(QueryOperator):
    def to_query(self, field_name, value):
        return {
            field_name: value
        }


# from http://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth
def update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def transform_query(document, **query):
    mongo_query = {}

    for key, value in sorted(query.items()):
        if key == 'raw':
            update(mongo_query, value)
            continue

        if '__' not in key:
            field = document.get_fields(key)[0]
            field_name = field.db_field
            operator = DefaultOperator()
            field_value = operator.get_value(field, value)
        else:
            values = key.split('__')
            field_reference_name, operator = ".".join(values[:-1]), values[-1]
            if operator not in OPERATORS:
                field_reference_name = "%s.%s" % (field_reference_name, operator)
                operator = ""

            fields = document.get_fields(field_reference_name)

            field_name = ".".join([
                hasattr(field, 'db_field') and field.db_field or field
                for field in fields
            ])
            operator = OPERATORS.get(operator, DefaultOperator)()
            field_value = operator.get_value(fields[-1], value)

        update(mongo_query, operator.to_query(field_name, field_value))

    return mongo_query


def validate_fields(document, query):
    from aiomotorengine.fields.embedded_document_field import EmbeddedDocumentField
    from aiomotorengine.fields.list_field import ListField

    for key, query in sorted(query.items()):
        if '__' not in key:
            fields = document.get_fields(key)
            operator = "equals"
        else:
            values = key.split('__')
            field_reference_name, operator = ".".join(values[:-1]), values[-1]
            if operator not in OPERATORS:
                field_reference_name = "%s.%s" % (field_reference_name, operator)
                operator = ""

            fields = document.get_fields(field_reference_name)

        is_none = (not fields) or (not all(fields))
        is_embedded = isinstance(fields[0], (EmbeddedDocumentField,))
        is_list = isinstance(fields[0], (ListField,))

        if is_none or (not is_embedded and not is_list and operator == ''):
            raise ValueError(
                "Invalid filter '%s': Invalid operator (if this is a sub-property, "
                "then it must be used in embedded document fields)." % key)
