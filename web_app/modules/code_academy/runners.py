"""Limited educational interpreters; never execute arbitrary Python or SQL writes."""
import ast
import operator
import sqlite3

BIN = {ast.Add:operator.add, ast.Sub:operator.sub, ast.Mult:operator.mul, ast.Div:operator.truediv, ast.FloorDiv:operator.floordiv, ast.Mod:operator.mod}
CMP = {ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.Gt:operator.gt,ast.LtE:operator.le,ast.GtE:operator.ge}

class SafePython:
    def __init__(self): self.env={}; self.lines=[]; self.functions={}; self.steps=0
    def tick(self):
        self.steps+=1
        if self.steps>300: raise ValueError('Превышен лимит учебных операций')
    def expr(self,n):
        self.tick()
        if isinstance(n,ast.Constant) and type(n.value) in (str,int,float,bool,type(None)): return n.value
        if isinstance(n,ast.Name): return self.env[n.id]
        if isinstance(n,ast.List): return [self.expr(v) for v in n.elts]
        if isinstance(n,ast.Tuple): return tuple(self.expr(v) for v in n.elts)
        if isinstance(n,ast.Subscript): return self.expr(n.value)[self.expr(n.slice)]
        if isinstance(n,ast.BinOp) and type(n.op) in BIN:
            a,b=self.expr(n.left),self.expr(n.right)
            if isinstance(a,(str,list,tuple)) and isinstance(b,int) and b>100: raise ValueError('Слишком большой результат')
            return BIN[type(n.op)](a,b)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd,ast.Not)):
            v=self.expr(n.operand); return -v if isinstance(n.op,ast.USub) else (+v if isinstance(n.op,ast.UAdd) else not v)
        if isinstance(n,ast.Compare):
            a=self.expr(n.left)
            for op,c in zip(n.ops,n.comparators):
                b=self.expr(c)
                if type(op) not in CMP or not CMP[type(op)](a,b): return False
                a=b
            return True
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
            if n.keywords: raise ValueError('Именованные аргументы пока не поддерживаются')
            name=n.func.id
            if name=='print':
                vals=[self.expr(a) for a in n.args]; self.lines.append(' '.join(map(str,vals))); return None
            if name in ('len','str','int','float') and len(n.args)==1:
                return {'len':len,'str':str,'int':int,'float':float}[name](self.expr(n.args[0]))
            if name in self.functions and not n.args:
                for stmt in self.functions[name]: self.stmt(stmt)
                return None
        raise ValueError('Эта конструкция пока не поддерживается учебным редактором')
    def stmt(self,n):
        self.tick()
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name): self.env[n.targets[0].id]=self.expr(n.value)
        elif isinstance(n,ast.Expr): self.expr(n.value)
        elif isinstance(n,ast.If):
            for s in (n.body if self.expr(n.test) else n.orelse): self.stmt(s)
        elif isinstance(n,ast.FunctionDef) and not n.args.args and not n.decorator_list: self.functions[n.name]=n.body
        elif isinstance(n,ast.Pass): pass
        else: raise ValueError('Эта инструкция пока не поддерживается учебным редактором')
    def run(self,code):
        if len(code)>5000: raise ValueError('Слишком длинный код')
        for stmt in ast.parse(code).body: self.stmt(stmt)
        result='\n'.join(self.lines)
        if len(result)>10000: raise ValueError('Слишком длинный вывод')
        return result

def run_python(code): return SafePython().run(code)

def run_sql(query):
    if len(query)>3000: raise ValueError('Слишком длинный запрос')
    # SQLite read-only query enforced via authorizer, not just regex.
    db=sqlite3.connect(':memory:')
    try:
        db.executescript('CREATE TABLE students(id INTEGER,name TEXT,faculty TEXT); INSERT INTO students VALUES (1,"Алия","Медицина"),(2,"Бек","Стоматология"),(3,"Дана","Медицина"); CREATE TABLE faculties(code TEXT,title TEXT); INSERT INTO faculties VALUES ("Медицина","Школа медицины"),("Стоматология","Школа стоматологии");')
        def authorize(action,*args):
            return sqlite3.SQLITE_OK if action in (sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION) else sqlite3.SQLITE_DENY
        db.set_authorizer(authorize)
        db.set_progress_handler(lambda: 1, 100000)
        cur=db.execute(query)
        rows=cur.fetchmany(101)
        if len(rows)>100: raise ValueError('Лимит: 100 строк')
        return '\n'.join(' | '.join(str(x) for x in row) for row in rows)
    finally: db.close()
