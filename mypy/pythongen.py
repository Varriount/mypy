from mypy.parse import none
from mypy.types import (
    Any, Instance, Void, TypeVar, TupleType, Callable, UnboundType, Type
)
from mypy.nodes import (
    IfStmt, ForStmt, WhileStmt, WithStmt, TryStmt, OverloadedFuncDef, FuncDef
)
from mypy.nodes import function_type
from mypy.output import OutputVisitor
from mypy.typerepr import ListTypeRepr


# Names present in mypy but not in Python. Imports of these names are removed
# during translation. These are generally type names, so references to these
# generally appear in declarations, which are erased during translation.
#
# TODO for many of these a corresponding alternative exists in Python; if
#      these names are used in a non-erased context (e.g. isinstance test or
#      overloaded method signature), we should change the reference to the
#      Python alternative
removed_import_names = {'re': ['Pattern', 'Match']}


# Some names defined in mypy builtins are defined in a different module in
# Python. We translate references to these names.
renamed_types = {'builtins.Sized': 'collections.Sized',
                 'builtins.Iterable': 'collections.Iterable',
                 'builtins.Iterator': 'collections.Iterator',
                 'builtins.Sequence': 'collections.Sequence',
                 'builtins.Mapping': 'collections.Mapping',
                 'builtins.Set': 'collections.Set',
                 're.Pattern': 're._pattern_type'}


# These types are erased during translation. If they are used in overloads,
# a hasattr check is used instead of an isinstance check (the value if the name
# of the attribute).
erased_duck_types = {
    'builtins.int_t': '__int__',
    'builtins.float_t': '__float__',
    'builtins.reversed_t': '__reversed__',
    'builtins.abs_t': '__abs__',
    'builtins.round_t': '__round__'
}


# Prefix used for generated names to avoid name clashes
PREFIX = '_m_'


# Some names need more complex logic to translate them. This dictionary maps
# qualified names to (initcode, newname) tuples. The initcode string is
# added to the module prolog.
#
# We use __ prefixes to avoid name clashes. Names starting with __ but not
# ending with _ are reserved for the implementation.
special_renamings = {
    're.Match': (['import re as %sre\n' % PREFIX,
                  'import builtins as %sbuiltins\n' % PREFIX,
                  '%sre_Match = %sbuiltins.type(%sre.match("", ""))\n' %
                  (PREFIX, PREFIX, PREFIX)],
                 '%sre_Match' % PREFIX)}


class PythonGenerator(OutputVisitor):
    """Python backend.

    Translate semantically analyzed parse trees to Python.  Reuse most
    of the generation logic from the mypy pretty printer implemented
    in OutputVisitor.
    """

    str[] prolog

    def __init__(self, pyversion=3):
        super().__init__()
        self.pyversion = pyversion
        self.prolog = []

    def output(self):
        """Return a string representation of the output."""
        # TODO add the prolog after the first comment and docstring
        return ''.join(self.prolog) + super().output()
    
    def visit_import_from(self, o):
        if o.id in removed_import_names:
            r = o.repr
            
            # Filter out any names not defined in Python from a
            # from ... import statement.
            
            toks = []
            comma = none
            for i in range(len(o.names)):
                if o.names[i][0] not in removed_import_names[o.id]:
                    toks.append(comma)
                    toks.extend(r.names[i][0])
                    comma = r.names[i][1]
            
            # If everything was filtered out, omit the statement.
            if toks:
                # Output the filtered statement.
                self.token(r.from_tok)
                self.tokens(r.components)
                self.token(r.import_tok)
                self.token(r.lparen)
                self.tokens(toks)
                self.token(r.rparen)
                self.token(r.br)
            elif self.block_depth > 0:
                # Can't just remove a statement if within a block.
                self.string(r.from_tok.pre + 'pass\n')
        else:
            super().visit_import_from(o)
    
    def visit_func_def(self, o, name_override=None):
        r = o.repr
        
        if r.def_tok and r.def_tok.string:
            self.token(r.def_tok)
        else:
            self.string(self.get_pre_whitespace(o.type.ret_type) + 'def')
        
        if name_override is None:
            self.token(r.name)
        else:
            self.string(' ' + name_override)
        self.function_header(o, r.args, o.arg_kinds, None, True, True)
        if not o.body.body:
            self.string(': pass' + '\n')
        else:
            self.node(o.body)
    
    def get_pre_whitespace(self, t):
        """Return whitespace before the first token of a type."""
        if isinstance(t, Any):
            return t.repr.any_tok.pre
        elif isinstance(t, Instance):
            if isinstance(t.repr, ListTypeRepr):
                return self.get_pre_whitespace(t.args[0])
            else:
                return t.repr.components[0].pre
        elif isinstance(t, Void):
            return t.repr.void.pre
        elif isinstance(t, TypeVar):
            return t.repr.name.pre
        elif isinstance(t, TupleType):
            return t.repr.components[0].pre
        elif isinstance(t, Callable):
            return t.repr.func.pre
        else:
            raise RuntimeError('Unsupported type {}'.format(t))
    
    def visit_var_def(self, o):
        r = o.repr
        if r:
            self.string(self.get_pre_whitespace(o.items[0].type))
            self.omit_next_space = True
            for v in o.items:
                self.node(v)
            if o.init:
                self.token(r.assign)
                self.node(o.init)
            else:
                self.string(' = {}'.format(', '.join(['None'] * len(o.items))))
            self.token(r.br)

    def visit_name_expr(self, o):
        # Rename some type references (e.g. Iterable -> collections.Iterable).
        renamed = self.get_renaming(o.fullname)
        if renamed:
            self.string(o.repr.id.pre)
            self.string(renamed)
        else:
            super().visit_name_expr(o)
    
    def visit_cast_expr(self, o):
        # Erase cast.
        self.string(o.repr.lparen.pre)
        self.node(o.expr)

    def visit_type_application(self, o):
        self.node(o.expr)
    
    def visit_for_stmt(self, o):
        r = o.repr
        self.token(r.for_tok)
        for i in range(len(o.index)):
            self.node(o.index[i])
            self.token(r.commas[i])
        self.token(r.in_tok)
        self.node(o.expr)
        
        self.node(o.body)
        if o.else_body:
            self.token(r.else_tok)
            self.node(o.else_body)
    
    def visit_type_def(self, o):
        r = o.repr
        self.string(r.class_tok.pre)
        self.string('class')
        self.token(r.name)

        # Erase references to base types such as int_t which do not exist in
        # Python.
        commas = []
        bases = []
        for i, base in enumerate(o.base_types):
            if (base.type.fullname() not in erased_duck_types
                    and base.repr):
                bases.append(base)
                if i < len(r.commas):
                    commas.append(r.commas[i])

        if bases:
            # Generate base types within parentheses.
            self.token(r.lparen)
            for i, base in enumerate(bases):
                self.string(self.erased_type(base))
                if i < len(bases) - 1:
                    self.token(commas[i])
            self.token(r.rparen)
        if not r.lparen.string and self.pyversion == 2:
            self.string('(object)')
        self.node(o.defs)
    
    def erased_type(self, t):
        """Return Python representation of a type (as string).

        Examples:
          - C -> 'C'
          - foo.Bar -> 'foo.Bar'
          - dict<x, y> -> 'dict'
          - Iterable<x> -> '<PREFIX>collections.Iterable' (also add import)
        """
        if isinstance(t, Instance) or isinstance(t, UnboundType):
            if isinstance(t.repr, ListTypeRepr):
                self.generate_import('builtins')
                return '%sbuiltins.list' % PREFIX
            else:
                # Some types need to be translated (e.g. Iterable).
                renamed = self.get_renaming(t.type.fullname())
                if renamed:
                    pre = t.repr.components[0].pre
                    return pre + renamed
                else:
                    a = []
                    if t.repr:
                        for tok in t.repr.components:
                            a.append(tok.rep())
                    return ''.join(a)
        elif isinstance(t, TupleType):
            return 'tuple' # FIX: aliasing?
        elif isinstance(t, TypeVar):
            return 'object' # Type variables are erased to "object"
        else:
            raise RuntimeError('Cannot translate type {}'.format(t))
    
    def visit_func_expr(self, o):
        r = o.repr
        self.token(r.lambda_tok)
        self.function_header(o, r.args, o.arg_kinds, None, True, False)
        self.token(r.colon)
        self.node(o.body.body[0].expr)
    
    void visit_overloaded_func_def(self, OverloadedFuncDef o):
        """Translate overloaded function definition.

        Overloaded functions are transformed into a single Python function that
        performs argument type checks and length checks to dispatch to the
        right implementation.
        """
        indent = self.indent * ' '
        first = o.items[0]
        r = first.repr
        # Emit "def".
        if r.def_tok and r.def_tok.string:
            self.token(r.def_tok)
        else:
            # TODO omit (some) comments; now comments may be duplicated
            sig = (Callable)first.type
            self.string(self.get_pre_whitespace(sig.ret_type) + 'def')
        # Emit function name and signature.
        self.string(' {}('.format(first.name()))
        self.extra_indent += 4
        fixed_args, optional, rest_args = self.make_overload_sig(o)
        self.string('):\n' + indent)
        # Emit function bodies of overload variants.
        for n, f in enumerate(o.items):
            self.visit_func_def(f, '{}{}'.format(f.name(), n + 1))
        self.string('\n')

        self.make_dispatcher(o, fixed_args, optional, rest_args)
        
        self.extra_indent -= 4
        last_stmt = o.items[-1].body.body[-1]
        self.token(self.find_break_after_statement(last_stmt))

    tuple<str[], str[], str> make_overload_sig(self, OverloadedFuncDef o):
        fixed_args, optional, is_more = get_overload_args(o)
        args = fixed_args[:]
        for i, arg in enumerate(optional):
            self.add_to_prolog('{} = object()\n'.format(default(i)))
            args.append('{}={}'.format(arg, default(i)))
        str rest_args = None
        if is_more:
            rest_args = make_unique('args', fixed_args)
            args.append('*{}'.format(rest_args))
        self.string(', '.join(args))
        return fixed_args, optional, rest_args

    void make_dispatcher(self, OverloadedFuncDef o, str[] fixed_args,
                         str[] optional_args, str rest_args):
        """Generate dispatching logic for an overloaded function."""
        indent = self.indent * ' '
        n = 1
        for i, fi in enumerate(o.items):
            for c, argc in self.make_overload_check(fi, fixed_args,
                                                    optional_args, rest_args):
                self.string(indent)
                if n == 1:
                    self.string('if ')
                else:
                    self.string('elif ')
                self.string(c)
                self.string(':' + '\n' + indent)
                self.string('    return {}'.format(make_overload_call(
                    fi, i + 1, argc, fixed_args, optional_args,
                    rest_args)) + '\n')
                n += 1
        self.string(indent + 'else:' + '\n')
        self.string(indent + '    raise TypeError("Invalid arguments")')

    tuple<str, int>[] make_overload_check(self, FuncDef f, str[] fixed_args,
                                          str[] optional_args, str rest_args):
        """Return (condition, arg count) tuples."""
        res = <tuple<str, int>> []
        sig = (Callable)function_type(f)
        for argc in range(sig.min_args, len(sig.arg_types) + 1):
            a = <str> []
            if rest_args:
                a.append(make_argument_count_check(f, len(fixed_args),
                                                   rest_args))
            i = 0
            for t in sig.arg_types[:argc]:
                if not isinstance(t, Any) and (t.repr or
                                               isinstance(t, Callable)):
                    a.append(self.make_argument_check(
                        argument_ref(i, fixed_args, optional_args, rest_args),
                        t))
                elif i >= len(fixed_args):
                    j = i - len(fixed_args)
                    a.append('{} is not {}'.format(optional_args[j],
                                                   default(j)))
                i += 1
            for i in range(argc - len(fixed_args), len(optional_args)):
                a.append('{} is {}'.format(optional_args[i], default(i)))
            if len(a) > 0:
                res.append((' and '.join(a), argc))
            else:
                res.append(('True', argc))
        return res

    str make_argument_check(self, str name, Type typ):
        if isinstance(typ, Callable):
            return 'callable({})'.format(name)
        if (isinstance(typ, Instance) and
                ((Instance)typ).type.fullname() in erased_duck_types):
            inst = (Instance)typ
            return "hasattr({}, '{}')".format(
                                name, erased_duck_types[inst.type.fullname()])
        else:
            cond = 'isinstance({}, {})'.format(name, self.erased_type(typ))
            return cond.replace('  ', ' ')
    
    str find_break_after_statement(self, any s):
        if isinstance(s, IfStmt):
            blocks = s.body + [s.else_body]
        elif isinstance(s, ForStmt) or isinstance(s, WhileStmt):
            blocks = [s.body, s.else_body]
        elif isinstance(s, WithStmt):
            blocks = [s.body]
        elif isinstance(s, TryStmt):
            blocks = s.handlers + [s.else_body, s.finally_body]
        else:
            return s.repr.br
        for b in reversed(blocks):
            if b:
                return self.find_break_after_statement(b.body[-1])
        raise RuntimeError('Could not find break after statement')
    
    def visit_list_expr(self, o):
        r = o.repr
        self.token(r.lbracket)
        self.comma_list(o.items, r.commas)
        self.token(r.rbracket)
    
    def visit_dict_expr(self, o):
        r = o.repr
        self.token(r.lbrace)
        i = 0
        for k, v in o.items:
            self.node(k)
            self.token(r.colons[i])
            self.node(v)
            if i < len(r.commas):
                self.token(r.commas[i])
            i += 1
        self.token(r.rbrace)

    def visit_super_expr(self, o):
        if self.pyversion > 2:
            super().visit_super_expr(o)
        else:
            r = o.repr
            self.tokens([r.super_tok, r.lparen])
            # TODO do not hard code 'self'
            self.string('%s, self' % o.info.name())
            self.tokens([r.rparen, r.dot, r.name])

    def generate_import(self, modid):
        """Generate an import in the file prolog.

        When importing, the module is given a '_m_' prefix. For example, an
        import of module 'foo' is generated as 'import foo as _m_foo'.
        """
        # TODO make sure that there is no name clash
        last_component = modid.split('.')[-1]
        self.add_to_prolog('import {} as _m_{}\n'.format(modid,
                                                         last_component))

    def generate_import_from_name(self, fullname):
        """Use module portion of a qualified name to generate an import."""
        modid = fullname[:fullname.rfind('.')]
        self.generate_import(modid)

    def add_to_prolog(self, string):
        """Add a line to the file prolog unless it already exists."""
        if not string in self.prolog:
            self.prolog.append(string)

    def get_renaming(self, fullname):
        """Determine the renaming target name of a qualified mypy name.

        Return None if the name needs no renaming; otherwise return the new
        name as a string.

        Also add any required imports, etc. to the file prolog.
        """
        renamed = renamed_types.get(fullname)
        if renamed:
            # Ordinary renaming. Import a module that defines the name and
            # rename the reference.
            self.generate_import_from_name(renamed)
            return PREFIX + renamed
        else:
            special = special_renamings.get(fullname)
            if special:
                # Special renaming. Add custom code to prolog and rename the
                # reference.
                prolog, renamed = special
                for line in prolog:
                    self.add_to_prolog(line)
                return renamed
            else:
                return None


tuple<str[], str[], bool> get_overload_args(OverloadedFuncDef o):
    """Return: fixed args, optional args, *args?."""
    fixed = <str> []
    min_fixed = 100000
    max_fixed = 0
    for f in o.items:
        if len(f.args) > len(fixed):
            for v in f.args[len(fixed):]:
                fixed.append(v.name())
        min_fixed = min(min_fixed, f.min_args)
        max_fixed = max(max_fixed, len(f.args))
    return fixed[:min_fixed], fixed[min_fixed:], False #max_fixed > min_fixed


str make_unique(str n, str[] others):
    """Modify name n as needed to make it distinct from names in others."""
    if n in others:
        return make_unique('_' + n, others)
    else:
        return n


str make_argument_count_check(FuncDef f, int num_fixed,
                              str rest_args):
    return 'len({}) == {}'.format(rest_args, f.min_args - num_fixed)


str make_overload_call(FuncDef f, int n, int argc, str[] fixed_args,
                       str[] optional_args, str rest_args):
    a = <str> []
    for i in range(argc):
        a.append(argument_ref(i, fixed_args, optional_args, rest_args))
    return '{}{}({})'.format(f.name(), n, ', '.join(a))


str argument_ref(int i, str[] fixed_args, str[] optional_args, str rest_args):
    if i < len(fixed_args):
        return fixed_args[i]
    elif i < len(fixed_args) + len(optional_args):
        return optional_args[i - len(fixed_args)]
    else:
        return '{}[{}]'.format(rest_args, i - len(fixed_args) -
                               len(optional_args))


str default(int n):
    return '%sdef%d' % (PREFIX, n)
