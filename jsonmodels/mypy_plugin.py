from typing import Callable, List, Type
import mypy
from mypy.plugin import Plugin, AttributeContext, FunctionContext
from mypy.types import Type as MypyType

class JSONModelsPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Callable[[AttributeContext], Type] | None:
        if fullname == "jsonmodels.fields.StringField":
            return self._string_field_callback
        if fullname == "jsonmodels.fields.IntField":
            return self._int_field_callback
        if fullname == "jsonmodels.fields.FloatField":
            return self._float_field_callback
        if fullname == "jsonmodels.fields.BoolField":
            return self._bool_field_callback
        if fullname == "jsonmodels.fields.TimeField":
            return self._time_field_callback
        if fullname == "jsonmodels.fields.DateField":
            return self._date_field_callback
        if fullname == "jsonmodels.fields.DateTimeField":
            return self._datetime_field_callback
        if fullname == "jsonmodels.fields.EmbeddedField":
            return self._embedded_field_callback
        if fullname == "jsonmodels.fields.ListField":
            return self._list_field_callback
        if fullname == "jsonmodels.fields.DerivedListField":
            return self._list_field_callback

        return None

    def _wrap_nullable(self, ctx: FunctionContext, core_type: MypyType) -> MypyType:
        try:
            nullable_index = ctx.callee_arg_names.index("nullable")
        except ValueError:
            return core_type

        arg_value = ctx.args[nullable_index]
        if len(arg_value) == 0:
            return core_type

        nullable_value = arg_value[0]
        if isinstance(nullable_value, mypy.nodes.NameExpr) and nullable_value.fullname == "builtins.True":
            return mypy.types.UnionType([core_type, mypy.types.NoneType()])

        return core_type

    def _string_field_callback(self, ctx: FunctionContext) -> MypyType:
        return self._wrap_nullable(ctx, ctx.api.named_type("builtins.str"))

    def _int_field_callback(self, ctx: FunctionContext) -> MypyType:
        return self._wrap_nullable(ctx, ctx.api.named_type("builtins.int"))

    def _float_field_callback(self, ctx: FunctionContext) -> MypyType:
        return self._wrap_nullable(ctx, ctx.api.named_type("builtins.float"))

    def _bool_field_callback(self, ctx: FunctionContext) -> MypyType:
        return self._wrap_nullable(ctx, ctx.api.named_type("builtins.bool"))

    def _time_field_callback(self, ctx: FunctionContext) -> MypyType:
        return self._wrap_nullable(ctx, ctx.api.named_type("datetime.time"))

    def _date_field_callback(self, ctx: FunctionContext) -> MypyType:
        return self._wrap_nullable(ctx, ctx.api.named_type("datetime.date"))

    def _datetime_field_callback(self, ctx: FunctionContext) -> MypyType:
        return self._wrap_nullable(ctx, ctx.api.named_type("datetime.datetime"))

    def _get_type_from_arg(self, ctx: FunctionContext, arg_name: str) -> MypyType:
        try:
            model_types_index = ctx.callee_arg_names.index(arg_name)
        except ValueError:
            return mypy.types.NoneType()

        arg_value = ctx.args[model_types_index]
        if len(arg_value) == 0:
            return mypy.types.NoneType()

        model_types_value = arg_value[0]

        if isinstance(model_types_value, mypy.nodes.NameExpr):
            return ctx.api.named_type(model_types_value.fullname)

        if isinstance(model_types_value, mypy.nodes.TupleExpr):
            accepted_types: List[MypyType] = []
            for item in model_types_value.items:
                if isinstance(item, mypy.nodes.NameExpr):
                    accepted_types.append(ctx.api.named_type(item.fullname))
            return mypy.types.UnionType(accepted_types)

        return mypy.types.NoneType()

    def _embedded_field_callback(self, ctx: FunctionContext) -> MypyType:
        return self._wrap_nullable(ctx, self._get_type_from_arg(ctx, "model_types"))

    def _list_field_callback(self, ctx: FunctionContext) -> MypyType:
        item_type = self._get_type_from_arg(ctx, "items_types")
        list_type = ctx.api.named_generic_type("list", [item_type])
        return self._wrap_nullable(ctx, list_type)

def plugin(version: str):
    return JSONModelsPlugin
