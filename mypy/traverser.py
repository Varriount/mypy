from mypy.visitor import NodeVisitor
from mypy.nodes import (
    Block, MypyFile, VarDef, FuncItem, CallExpr
)


class TraverserVisitor<T>(NodeVisitor<T>):
    """A parse tree visitor that traverses the parse tree during visiting.

    It does not peform any actions outside the travelsal. Subclasses
    should override visit methods to perform actions during
    travelsal. Calling the superclass method allows reusing the
    travelsal implementation.
    """

    # TODO add static types everywhere
    
    # Helper methods
    
    void accept_block(self, Block block):
        self.visit_block(block)
        for s in block.body:
            s.accept(self)
    
    # Visit methods
    
    T visit_mypy_file(self, MypyFile o):
        for d in o.defs:
            d.accept(self)
    
    T visit_func(self, FuncItem o):
        for i in o.init:
            if i is not None:
                i.accept(self)
        for v in o.args:
            self.visit_var(v)
        self.accept_block(o.body)
    
    def visit_func_def(self, o):
        self.visit_func(o)
    
    def visit_type_def(self, o):
        for d in o.defs:
            d.accept(self)
    
    def visit_decorator(self, o):
        o.func.accept(self)
        o.decorator.accept(self)
    
    T visit_var_def(self, VarDef o):
        if o.init is not None:
            o.init.accept(self)
        for v in o.items:
            self.visit_var(v)
    
    def visit_expression_stmt(self, o):
        o.expr.accept(self)
    
    def visit_assignment_stmt(self, o):
        o.rvalue.accept(self)
        for l in o.lvalues:
            l.accept(self)
    
    def visit_operator_assignment_stmt(self, o):
        o.rvalue.accept(self)
        o.lvalue.accept(self)
    
    def visit_while_stmt(self, o):
        o.expr.accept(self)
        self.accept_block(o.body)
        if o.else_body is not None:
            self.accept_block(o.else_body)
    
    def visit_for_stmt(self, o):
        for ind in o.index:
            ind.accept(self)
        o.expr.accept(self)
        self.accept_block(o.body)
        if o.else_body is not None:
            self.accept_block(o.else_body)
    
    def visit_return_stmt(self, o):
        if o.expr is not None:
            o.expr.accept(self)
    
    def visit_assert_stmt(self, o):
        if o.expr is not None:
            o.expr.accept(self)
    
    def visit_yield_stmt(self, o):
        if o.expr is not None:
            o.expr.accept(self)
    
    def visit_del_stmt(self, o):
        if o.expr is not None:
            o.expr.accept(self)
    
    def visit_if_stmt(self, o):
        for e in o.expr:
            e.accept(self)
        for b in o.body:
            self.accept_block(b)
        if o.else_body is not None:
            self.accept_block(o.else_body)
    
    def visit_raise_stmt(self, o):
        if o.expr is not None:
            o.expr.accept(self)
        if o.from_expr is not None:
            o.from_expr.accept(self)
    
    def visit_try_stmt(self, o):
        self.accept_block(o.body)
        for i in range(len(o.types)):
            o.types[i].accept(self)
            self.accept_block(o.handlers[i])
        if o.else_body is not None:
            self.accept_block(o.else_body)
        if o.finally_body is not None:
            self.accept_block(o.finally_body)
    
    def visit_with_stmt(self, o):
        for i in range(len(o.expr)):
            o.expr[i].accept(self)
            if o.name[i] is not None:
                o.name[i].accept(self)
        self.accept_block(o.body)
    
    def visit_paren_expr(self, o):
        o.expr.accept(self)
    
    def visit_member_expr(self, o):
        o.expr.accept(self)
    
    T visit_call_expr(self, CallExpr o):
        for a in o.args:
            a.accept(self)
        o.callee.accept(self)
    
    def visit_op_expr(self, o):
        o.left.accept(self)
        o.right.accept(self)
    
    def visit_slice_expr(self, o):
        if o.begin_index is not None:
            o.begin_index.accept(self)
        if o.end_index is not None:
            o.end_index.accept(self)
        if o.stride is not None:
            o.stride.accept(self)
    
    def visit_cast_expr(self, o):
        o.expr.accept(self)
    
    def visit_unary_expr(self, o):
        o.expr.accept(self)
    
    def visit_list_expr(self, o):
        for item in o.items:
            item.accept(self)
    
    def visit_tuple_expr(self, o):
        for item in o.items:
            item.accept(self)
    
    def visit_dict_expr(self, o):
        for k, v in o.items:
            k.accept(self)
            v.accept(self)
    
    def visit_set_expr(self, o):
        for item in o.items:
            item.aceept(self)
    
    def visit_index_expr(self, o):
        o.base.accept(self)
        o.index.accept(self)
    
    def visit_generator_expr(self, o):
        o.left_expr.accept(self)
        o.right_expr.accpet(self)
        if o.condition is not None:
            o.condition.accept(self)
        for index in o.index:
            self.visit_var(index)
    
    def visit_list_comprehension(self, o):
        o.generator.accept(self)
    
    def visit_conditional_expr(self, o):
        o.cond.accept(self)
        o.if_expr.accept(self)
        o.else_expr.accept(self)
    
    def visit_type_application(self, o):
        o.expr.accept(self)
    
    def visit_func_expr(self, o):
        self.visit_func(o)
    
    def visit_filter_node(self, o):
        # These are for convenience. These node types are not defined in the
        # parser module.
        pass
