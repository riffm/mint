" Vim filetype plugin file
" Language: mint
" Maintainer: Tim Perevezentsev <riffm2005@gmail.com>

if version < 600
  syntax clear
elseif exists("b:current_syntax")
  finish
endif


syn keyword mintStatement    break continue del
syn keyword mintStatement    except exec finally
syn keyword mintStatement    pass print raise
syn keyword mintStatement    return try with
syn keyword mintStatement    global assert
syn keyword mintStatement    lambda yield
syn match mintStatement    /^#base:/
syn match mintStatement    /^\s*#/ nextgroup=mintFunction skipwhite
syn match mintStatement    /^\s*#def/ nextgroup=mintFunction skipwhite
syn match   mintTag    /\s*@/ display nextgroup=mintFunction skipwhite
syn match   mintTag    /^\s*@+[a-zA-Z_][a-zA-Z0-9_:-]*/ display contains=mintFunction
syn match   mintTag    /^\s*@\.[a-zA-Z_][a-zA-Z0-9_:-]*/ display contains=mintFunction
syn match   mintFunction    "[a-zA-Z_][a-zA-Z0-9_:-]*" contained nextgroup=mintAttribute
syn match   mintAttribute    "\.[a-zA-Z_][a-zA-Z0-9_:-]*" contained nextgroup=mintAttributeValue
syn region  mintAttributeValue     start=/(/ end=/)/ contains=mintStatement,mintPythonRepeat,mintVariable nextgroup=mintAttribute,mintTag

syn region mintVariable     start=/{{/ end=/}}/ contains=mintStatement,mintPythonRepeat,mintException
syn match mintRepeat    /^\s*#for \(.*\):$/
syn keyword mintPythonRepeat    for while contained
syn match mintConditional    /^\s*#if \(.*\):$/
syn match mintConditional    /^\s*#elif \(.*\):$/
syn match mintConditional    /^\s*#else:$/
syn keyword mintOperator    and in is not or
syn match   mintComment    "--.*$" contains=mintTodo,@Spell
syn match   mintComment    /^\s*\/\/.*$/
syn match   mintEscape    "\\.*$" contains=@Spell
syn keyword mintTodo        TODO FIXME XXX contained

" strings
syn match  mintEscape        +\\[abfnrtv'"\\]+ contained
syn match  mintEscape        "\\\o\{1,3}" contained
syn match  mintEscape        "\\x\x\{2}" contained
syn match  mintEscape        "\(\\u\x\{4}\|\\U\x\{8}\)" contained
syn match  mintEscape        "\\$"

if exists("mint_highlight_all")
  let mint_highlight_numbers = 1
  let mint_highlight_builtins = 1
  let mint_highlight_exceptions = 1
  let mint_highlight_space_errors = 1
endif

if exists("mint_highlight_numbers")
  " numbers (including longs and complex)
  syn match   mintNumber    "\<0x\x\+[Ll]\=\>"
  syn match   mintNumber    "\<\d\+[LljJ]\=\>"
  syn match   mintNumber    "\.\d\+\([eE][+-]\=\d\+\)\=[jJ]\=\>"
  syn match   mintNumber    "\<\d\+\.\([eE][+-]\=\d\+\)\=[jJ]\=\>"
  syn match   mintNumber    "\<\d\+\.\d\+\([eE][+-]\=\d\+\)\=[jJ]\=\>"
endif

if exists("mint_highlight_builtins")
  " builtin functions, types and objects, not really part of the syntax
  syn keyword mintBuiltin    True False bool enumerate set frozenset help
  syn keyword mintBuiltin    reversed sorted sum
  syn keyword mintBuiltin    Ellipsis None NotImplemented __import__ abs
  syn keyword mintBuiltin    apply buffer callable chr classmethod cmp
  syn keyword mintBuiltin    coerce compile complex delattr dict dir divmod
  syn keyword mintBuiltin    eval execfile file filter float getattr globals
  syn keyword mintBuiltin    hasattr hash hex id input int intern isinstance
  syn keyword mintBuiltin    issubclass iter len list locals long map max
  syn keyword mintBuiltin    min object oct open ord pow property range
  syn keyword mintBuiltin    raw_input reduce reload repr round setattr
  syn keyword mintBuiltin    slice staticmethod str super tuple type unichr
  syn keyword mintBuiltin    unicode vars xrange zip
endif

if exists("mint_highlight_exceptions")
  " builtin exceptions and warnings
  syn keyword mintException    ArithmeticError AssertionError AttributeError contained
  syn keyword mintException    DeprecationWarning EOFError EnvironmentError contained
  syn keyword mintException    Exception FloatingPointError IOError contained
  syn keyword mintException    ImportError IndentationError IndexError contained
  syn keyword mintException    KeyError KeyboardInterrupt LookupError contained
  syn keyword mintException    MemoryError NameError NotImplementedError contained
  syn keyword mintException    OSError OverflowError OverflowWarning contained
  syn keyword mintException    ReferenceError RuntimeError RuntimeWarning contained
  syn keyword mintException    StandardError StopIteration SyntaxError contained
  syn keyword mintException    SyntaxWarning SystemError SystemExit TabError contained
  syn keyword mintException    TypeError UnboundLocalError UnicodeError contained
  syn keyword mintException    UnicodeEncodeError UnicodeDecodeError contained
  syn keyword mintException    UnicodeTranslateError contained
  syn keyword mintException    UserWarning ValueError Warning WindowsError contained
  syn keyword mintException    ZeroDivisionError contained
endif

if exists("mint_highlight_space_errors")
  " trailing whitespace
  syn match   mintSpaceError   display excludenl "\S\s\+$"ms=s+1
  " mixed tabs and spaces
  syn match   mintSpaceError   display " \+\t"
  syn match   mintSpaceError   display "\t\+ "
endif

" This is fast but code inside triple quoted strings screws it up. It
" is impossible to fix because the only way to know if you are inside a
" triple quoted string is to start from the beginning of the file. If
" you have a fast machine you can try uncommenting the "sync minlines"
" and commenting out the rest.
syn sync match mintSync grouphere NONE "):$"
syn sync maxlines=200
"syn sync minlines=2000

if version >= 508 || !exists("did_mint_syn_inits")
  if version <= 508
    let did_mint_syn_inits = 1
    command -nargs=+ HiLink hi link <args>
  else
    command -nargs=+ HiLink hi def link <args>
  endif

  " The default methods for highlighting.  Can be overridden later
  HiLink mintStatement    Statement
  HiLink mintAttribute    Function
  HiLink mintFunction     Function
  HiLink mintTag          Function
  HiLink mintConditional    Conditional
  HiLink mintRepeat        Repeat
  HiLink mintPythonRepeat  Repeat
  HiLink mintEscape        Special
  HiLink mintOperator        Operator
  HiLink mintComment         Comment
  HiLink mintTodo            Todo
  HiLink mintVariable        Statement
  if exists("mint_highlight_numbers")
    HiLink mintNumber    Number
  endif
  if exists("mint_highlight_builtins")
    HiLink mintBuiltin    Function
  endif
  if exists("mint_highlight_exceptions")
    HiLink mintException    Exception
  endif
  if exists("mint_highlight_space_errors")
    HiLink mintSpaceError    Error
  endif

  delcommand HiLink
endif

let b:current_syntax = "mint"

" vim: ts=8

