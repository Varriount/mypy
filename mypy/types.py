"""Classes for representing mypy types."""

import mypy.nodes


class Type(mypy.nodes.Context):
    """Abstract base class for all types."""
    int line
    any repr
    
    void __init__(self, int line=-1, repr=None):
        self.line = line
        self.repr = repr

    int get_line(self):
        return self.line
    
    T accept<T>(self, TypeVisitor<T> visitor):
        raise RuntimeError('Not implemented')
    
    str __repr__(self):
        return self.accept(TypeStrVisitor())


class UnboundType(Type):
    """Instance type that has not been bound during semantic analysis."""
    str name
    Type[] args
    
    void __init__(self, str name, Type[] args=None, int line=-1,
                  any repr=None):
        if not args:
            args = []
        self.name = name
        self.args = args
        super().__init__(line, repr)
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_unbound_type(self)


class ErrorType(Type):
    """The error type is only used as a result of join and meet
    operations, when the result is undefined.
    """
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_error_type(self)


class Any(Type):
    """The type "any"."""
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_any(self)


class Void(Type):
    """The return type 'void'. This can only be used as the return type in a
    callable type and as the result type of calling such callable.
    """
    str source   # May be None; function that generated this value
    
    void __init__(self, str source=None, int line=-1, any repr=None):
        self.source = source
        super().__init__(line, repr)
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_void(self)
    
    Void with_source(self, str source):
        return Void(source, self.line, self.repr)


class NoneTyp(Type):
    """The type of 'None'. This is only used internally during type
    inference.  Programs cannot declare a variable of this type, and
    the type checker refuses to infer this type for a
    variable. However, subexpressions often have this type. Note that
    this is not used as the result type when calling a function with a
    void type, even though semantically such a function returns a None
    value; the void type is used instead so that we can report an
    error if the caller tries to do anything with the return value.
    """
    void __init__(self, int line=-1, repr=None):
        super().__init__(line, repr)
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_none_type(self)


class ErasedType(Type):
    """Placeholder for an erased type.

    This is used during type inference. This has the special property that
    it is ignored during type inference.
    """
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_erased_type(self)


class Instance(Type):
    """An instance type of form C<T1, ..., Tn>. Type variables Tn may
    be empty"""
    mypy.nodes.TypeInfo type
    Type[] args
    bool erased      # True if result of type variable substitution
    
    void __init__(self, mypy.nodes.TypeInfo typ, Type[] args, int line=-1,
                  any repr=None, any erased=False):
        self.type = typ
        self.args = args
        self.erased = erased
        super().__init__(line, repr)
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_instance(self)


BOUND_VAR = 2
OBJECT_VAR = 3


class TypeVar(Type):
    """A type variable type. This refers to either a class type variable
    (id > 0) or a function type variable (id < 0).
    """
    str name # Name of the type variable (for messages and debugging)
    int id # 1, 2, ... for type-related, -1, ... for function-related
    
    # True if refers to the value of the type variable stored in a generic
    # instance wrapper. This is only relevant for generic class wrappers. If
    # False (default), this refers to the type variable value(s) given as the
    # implicit type variable argument.
    #
    # Can also be BoundVar/ObjectVar TODO better representation
    any is_wrapper_var
    
    void __init__(self, str name, int id, any is_wrapper_var=False,
                  int line=-1, any repr=None):
        self.name = name
        self.id = id
        self.is_wrapper_var = is_wrapper_var
        super().__init__(line, repr)
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_type_var(self)


class FunctionLike(Type):
    """Abstract base class for function types (Callable and
    OverloadedCallable)."""
    bool is_type_obj(self): # Abstract
        pass
    
    Callable[] items(self): # Abstract
        pass
    
    Type with_name(self, str name): # Abstract
        pass


class Callable(FunctionLike):
    """Type of a non-overloaded callable object (function)."""
    Type[] arg_types # Types of function arguments
    int[] arg_kinds  # mypy.nodes.ARG_ constants
    str[] arg_names  # None if not a keyword argument
    int minargs         # Minimum number of arguments
    bool is_var_arg     # Is it a varargs function?
    Type ret_type       # Return value type
    str name            # Name (may be None; for error messages)
    TypeVars variables  # Type variables for a generic function
    
    # Implicit bound values of type variables. These can be either for
    # class type variables or for generic function type variables.
    # For example, the method 'append' of int[] has implicit value 'int' for
    # the list type variable; the explicit method type is just
    # 'void append(int)', without any type variable. Implicit values are needed
    # for runtime type checking, but they do not affect static type checking.
    #
    # All class type arguments must be stored first, ordered by id,
    # and function type arguments must be stored next, again ordered by id
    # (absolute value this time).
    #
    # Stored as tuples (id, type).
    tuple<int, Type>[] bound_vars
    
    bool _is_type_obj # Does this represent a type object?
    
    void __init__(self, Type[] arg_types, int[] arg_kinds, str[] arg_names,
                  Type ret_type, bool is_type_obj, str name=None,
                  TypeVars variables=None,
                  tuple<int, Type>[] bound_vars=None,
                  int line=-1, any repr=None):
        if not variables:
            variables = TypeVars([])
        if not bound_vars:
            bound_vars = []
        self.arg_types = arg_types
        self.arg_kinds = arg_kinds
        self.arg_names = arg_names
        self.min_args = arg_kinds.count(mypy.nodes.ARG_POS)
        self.is_var_arg = mypy.nodes.ARG_STAR in arg_kinds
        self.ret_type = ret_type
        self._is_type_obj = is_type_obj
        assert not name or '<bound method' not in name
        self.name = name
        self.variables = variables
        self.bound_vars = bound_vars
        super().__init__(line, repr)
    
    bool is_type_obj(self):
        return self._is_type_obj
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_callable(self)
    
    Callable with_name(self, str name):
        """Return a copy of this type with the specified name."""
        ret = self.ret_type
        if isinstance(ret, Void):
            ret = ((Void)ret).with_source(name)
        return Callable(self.arg_types,
                        self.arg_kinds,
                        self.arg_names,
                        ret,
                        self.is_type_obj(),
                        name,
                        self.variables,
                        self.bound_vars,
                        self.line, self.repr)
    
    int max_fixed_args(self):
        n = len(self.arg_types)
        if self.is_var_arg:
            n -= 1
        return n
    
    Callable[] items(self):
        return [self]
    
    bool is_generic(self):
        return self.variables.items != []
    
    int[] type_var_ids(self):
        int[] a = []
        for tv in self.variables.items:
            a.append(tv.id)
        return a


class Overloaded(FunctionLike):
    """Overloaded function type T1, ... Tn, where each Ti is Callable.
    
    The variant to call is chosen based on runtime argument types; the first
    matching signature is the target.
    """
    Callable[] _items # Must not be empty
    
    void __init__(self, Callable[] items):
        self._items = items
        super().__init__(items[0].line, None)
    
    Callable[] items(self):
        return self._items
    
    str name(self):
        return self._items[0].name
    
    bool is_type_obj(self):
        # All the items must have the same type object status, so it's
        # sufficient to query only one of them.
        return self._items[0].is_type_obj()
    
    Overloaded with_name(self, str name):
        Callable[] ni = []
        for it in self._items:
            ni.append(it.with_name(name))
        return Overloaded(ni)
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_overloaded(self)


class TupleType(Type):
    """The tuple type tuple<T1, ..., Tn> (at least one type argument)."""
    Type[] items
    
    void __init__(self, Type[] items, int line=-1, any repr=None):
        self.items = items
        super().__init__(line, repr)
    
    int length(self):
        return len(self.items)
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_tuple_type(self)


class TypeVars:
    """Representation of type variables of a function or type (i.e.
    <T1 [: B1], ..., Tn [: Bn]>).

    TODO bounds are not supported, but they may be supported in future
    """    
    TypeVarDef[] items
    any repr
    
    void __init__(self, TypeVarDef[] items, any repr=None):
        self.items = items
        self.repr = repr
    
    str __repr__(self):
        if self.items == []:
            return ''
        str[] a = []
        for v in self.items:
            a.append(str(v))
        return '<{}>'.format(', '.join(a))


class TypeVarDef(mypy.nodes.Context):
    """Definition of a single type variable, with an optional bound
    (for bounded polymorphism).
    """
    str name
    int id
    Type bound  # May be None
    int line
    any repr
    
    void __init__(self, str name, int id, Type bound=None, int line=-1,
                  any repr=None):
        self.name = name
        self.id = id
        self.bound = bound
        self.line = line
        self.repr = repr

    int get_line(self):
        return self.line
    
    str __repr__(self):
        if self.bound is None:
            return str(self.name)
        else:
            return '{} is {}'.format(self.name, self.bound)


class RuntimeTypeVar(Type):
    """Reference to a runtime variable that represents the value of a type
    variable. The reference can must be a expression node, but only some
    node types are properly supported (NameExpr, MemberExpr and IndexExpr
    mainly).
    """
    mypy.nodes.Node node
    
    void __init__(self, mypy.nodes.Node node):
        self.node = node
        super().__init__(-1, None)
    
    T accept<T>(self, TypeVisitor<T> visitor):
        return visitor.visit_runtime_type_var(self)


#
# Visitor-related classes
#


class TypeVisitor<T>:
    """Visitor class for types (Type subclasses).

    The parameter T is the return type of the visit methods.
    """
    T visit_unbound_type(self, UnboundType t):
        pass
    
    T visit_error_type(self, ErrorType t):
        pass
    
    T visit_any(self, Any t):
        pass
    
    T visit_void(self, Void t):
        pass
    
    T visit_none_type(self, NoneTyp t):
        pass
    
    T visit_erased_type(self, ErasedType t):
        pass
    
    T visit_type_var(self, TypeVar t):
        pass
    
    T visit_instance(self, Instance t):
        pass
    
    T visit_callable(self, Callable t):
        pass
    
    T visit_overloaded(self, Overloaded t):
        pass
    
    T visit_tuple_type(self, TupleType t):
        pass
    
    T visit_runtime_type_var(self, RuntimeTypeVar t):
        pass


class TypeTranslator(TypeVisitor<Type>):
    """Identity type transformation.

    Subclass this and override some methods to implement a non-trivial
    transformation.
    """
    Type visit_unbound_type(self, UnboundType t):
        return t
    
    Type visit_error_type(self, ErrorType t):
        return t
    
    Type visit_any(self, Any t):
        return t
    
    Type visit_void(self, Void t):
        return t
    
    Type visit_none_type(self, NoneTyp t):
        return t
    
    Type visit_erased_type(self, ErasedType t):
        return t
    
    Type visit_instance(self, Instance t):
        return Instance(t.type, self.translate_types(t.args), t.line, t.repr)
    
    Type visit_type_var(self, TypeVar t):
        return t
    
    Type visit_callable(self, Callable t):
        return Callable(self.translate_types(t.arg_types),
                        t.arg_kinds,
                        t.arg_names,
                        t.ret_type.accept(self),
                        t.is_type_obj(),
                        t.name,
                        self.translate_variables(t.variables),
                        self.translate_bound_vars(t.bound_vars),
                        t.line, t.repr)
    
    Type visit_tuple_type(self, TupleType t):
        return TupleType(self.translate_types(t.items), t.line, t.repr)
    
    Type[] translate_types(self, Type[] types):
        return [t.accept(self) for t in types]
    
    tuple<int, Type>[] translate_bound_vars(self,
                                            tuple<int, Type>[] types):
        return [(id, t.accept(self)) for id, t in types]

    TypeVars translate_variables(self, TypeVars variables):
        return variables


class TypeStrVisitor(TypeVisitor<str>):
    """Visitor for pretty-printing types into strings.

    Do not preserve original formatting.
    
    Notes:
     - Include implicit bound type variables of callables.
     - Represent unbound types as Foo? or Foo?<...>.
     - Represent the NoneTyp type as None.
    """
    def visit_unbound_type(self, t):
        s = t.name + '?'
        if t.args != []:
            s += '<{}>'.format(self.list_str(t.args))
        return s
    
    def visit_error_type(self, t):
        return '<ERROR>'
    
    def visit_any(self, t):
        return 'any'
    
    def visit_void(self, t):
        return 'void'
    
    def visit_none_type(self, t):
        # Include quotes to make this distinct from the None value.
        return "'None'"
    
    def visit_erased_type(self, t):
        return "<Erased>"
    
    def visit_instance(self, t):
        s = t.type.fullname()
        if t.erased:
            s += '*'
        if t.args != []:
            s += '<{}>'.format(self.list_str(t.args))
        return s
    
    def visit_type_var(self, t):
        if t.name is None:
            # Anonymous type variable type (only numeric id).
            return '`{}'.format(t.id)
        else:
            # Named type variable type.
            s = '{}`{}'.format(t.name, t.id)
            if t.is_wrapper_var == BOUND_VAR:
                s += '!B'
            elif t.is_wrapper_var == True:
                s += '!W'
            elif t.is_wrapper_var == OBJECT_VAR:
                s += '!O'
            return s
    
    def visit_callable(self, t):
        s = ''
        bare_asterisk = False
        for i in range(len(t.arg_types)):
            if s != '':
                s += ', '
            if t.arg_kinds[i] == mypy.nodes.ARG_NAMED and not bare_asterisk:
                s += '*, '
                bare_asterisk = True
            if t.arg_kinds[i] == mypy.nodes.ARG_STAR:
                s += '*'
            s += str(t.arg_types[i])
            if t.arg_kinds[i] == mypy.nodes.ARG_STAR2:
                s += '**'
            if t.arg_names[i]:
                if s.endswith('**'):
                    s = s[:-2] + ' **'
                else:
                    s += ' '
                s += t.arg_names[i]
            if t.arg_kinds[i] == mypy.nodes.ARG_OPT:
                s += '='
        
        s = '({})'.format(s)
        
        if not isinstance(t.ret_type, Void):
            s += ' -> {}'.format(t.ret_type)
        
        if t.variables.items != []:
            s = '{} {}'.format(t.variables, s)
        
        if t.bound_vars != []:
            # Include implicit bound type variables.
            a = []
            for i, bt in t.bound_vars:
                a.append('{}:{}'.format(i, bt))
            s = '[{}] {}'.format(', '.join(a), s)
        
        return 'def {}'.format(s)
    
    def visit_overloaded(self, t):
        a = []
        for i in t.items():
            a.append(i.accept(self))
        return 'Overload({})'.format(', '.join(a))
    
    def visit_tuple_type(self, t):
        s = self.list_str(t.items)
        return 'tuple<{}>'.format(s)
    
    def visit_runtime_type_var(self, t):
        return '<RuntimeTypeVar>'
    
    def list_str(self, a):
        """Convert items of an array to strings (pretty-print types)
        and join the results with commas.
        """
        res = []
        for t in a:
            if isinstance(t, Type):
                res.append(t.accept(self))
            else:
                res.append(str(t))
        return ', '.join(res)


# These constants define the method used by TypeQuery to combine multiple
# query results, e.g. for tuple types. The strategy is not used for empty
# result lists; in that case the default value takes precedence.
ANY_TYPE_STRATEGY = 0   # Return True if any of the results are True.
ALL_TYPES_STRATEGY = 1  # Return True if all of the results are True.


class TypeQuery(TypeVisitor<bool>):
    """Visitor for performing simple boolean queries of types.

    This class allows defining the default value for leafs to simplify the
    implementation of many queries.
    """
    bool default  # Default result
    int strategy  # Strategy for combining multiple values
    
    void __init__(self, bool default, int strategy):
        """Construct a query visitor with the given default result and
        strategy for combining multiple results. The strategy must be either
        ANY_TYPE_STRATEGY or ALL_TYPES_STRATEGY.
        """
        self.default = default
        self.strategy = strategy
    
    bool visit_unbound_type(self, UnboundType t):
        return self.default
    
    bool visit_error_type(self, ErrorType t):
        return self.default
    
    bool visit_any(self, Any t):
        return self.default
    
    bool visit_void(self, Void t):
        return self.default
    
    bool visit_none_type(self, NoneTyp t):
        return self.default
    
    bool visit_erased_type(self, ErasedType t):
        return self.default
    
    bool visit_type_var(self, TypeVar t):
        return self.default
    
    bool visit_instance(self, Instance t):
        return self.query_types(t.args)
    
    bool visit_callable(self, Callable t):
        # FIX generics
        return self.query_types(t.arg_types + [t.ret_type])
    
    bool visit_tuple_type(self, TupleType t):
        return self.query_types(t.items)
    
    bool visit_runtime_type_var(self, RuntimeTypeVar t):
        return self.default
    
    bool query_types(self, Type[] types):
        """Perform a query for a list of types.

        Use the strategy constant to combine the results.
        """
        if not types:
            # Use default result for empty list.
            return self.default
        if self.strategy == ANY_TYPE_STRATEGY:
            # Return True if at least one component is true.
            res = False
            for t in types:
                res = res or t.accept(self)
                if res:
                    break
            return res
        else:
            # Return True if all components are true.
            res = True
            for t in types:
                res = res and t.accept(self)
                if not res:
                    break
            return res


class BasicTypes:
    """Collection of Instance types of basic types (object, type, etc.)."""
    void __init__(self, Instance object, Instance type_type, Type tuple,
                  Type function):
        self.object = object
        self.type_type = type_type
        self.tuple = tuple
        self.function = function


Type strip_type(Type typ):
    """Make a copy of type without 'debugging info' (function name)."""
    if isinstance(typ, Callable):
        ctyp = (Callable)typ
        return Callable(ctyp.arg_types,
                        ctyp.arg_kinds,
                        ctyp.arg_names,
                        ctyp.ret_type,
                        ctyp.is_type_obj(),
                        None,
                        ctyp.variables)
    elif isinstance(typ, Overloaded):
        overload = (Overloaded)typ
        return Overloaded([(Callable)strip_type(t)
                           for t in overload.items()])
    else:
        return typ


Callable replace_self_type(Callable t, Type self_type):
    """Return a copy of a callable type with a different self argument type.

    Assume that the callable is the signature of a method.
    """
    return Callable([self_type] + t.arg_types[1:],
                    t.arg_kinds,
                    t.arg_names,
                    t.ret_type,
                    t.is_type_obj(),
                    t.name,
                    t.variables,
                    t.bound_vars,
                    t.line, None)
