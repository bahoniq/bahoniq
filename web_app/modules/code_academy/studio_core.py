"""Safe educational project model, preview extraction, syntax checks."""
import ast
import json
import re
from pathlib import Path
from .builder import GuidedProject, line_explanation

DEFAULTS = {'TITLE':'Task Academy','WIDTH':760,'HEIGHT':520,'ACCENT':'#009246','BUTTON_TEXT':'Добавить','LABEL_TEXT':'Список задач'}
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')

def preview_settings(files):
    settings = dict(DEFAULTS)
    config = ast.parse(files.get('settings.py',files.get('config.py','')))
    for node in ast.walk(config):
        if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name):
            key={'title':'TITLE','width':'WIDTH','height':'HEIGHT','accent':'ACCENT'}.get(node.target.id)
            if key:
                try: settings[key]=ast.literal_eval(node.value)
                except (ValueError,TypeError,SyntaxError,MemoryError,RecursionError): pass
        elif isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            key=node.targets[0].id
            if key in settings:
                try: settings[key]=ast.literal_eval(node.value)
                except (ValueError,TypeError,SyntaxError,MemoryError,RecursionError): pass
    ui=files.get('ui/main_window.py','')
    for key,pattern in [('BUTTON_TEXT',r'tk\.Button\([^\n]*?text\s*=\s*([\'\"][^\'\"]*[\'\"])'),('LABEL_TEXT',r'tk\.Label\([^\n]*?text\s*=\s*([\'\"][^\'\"]*[\'\"])')]:
        m=re.search(pattern,ui)
        if m:
            try: settings[key]=ast.literal_eval(m.group(1))
            except (SyntaxError,ValueError): pass
    settings['WIDTH']=max(320,min(1400,int(settings['WIDTH']))) if str(settings['WIDTH']).isdigit() else 700
    settings['HEIGHT']=max(200,min(1000,int(settings['HEIGHT']))) if str(settings['HEIGHT']).isdigit() else 450
    if not isinstance(settings['ACCENT'],str) or not HEX.fullmatch(settings['ACCENT']): settings['ACCENT']=DEFAULTS['ACCENT']
    for key in ('TITLE','BUTTON_TEXT','LABEL_TEXT'):
        settings[key]=str(settings[key])[:90]
    return settings

def apply_visual_settings(project, title, width, height, accent, button_text, label_text):
    if not HEX.fullmatch(accent): raise ValueError('Цвет должен быть #RRGGBB')
    width=int(width);height=int(height)
    if not 320<=width<=1400 or not 200<=height<=1000: raise ValueError('Недопустимый размер окна')
    config_name='settings.py' if 'settings.py' in project.files else 'config.py'
    config=project.files[config_name]
    if config_name=='settings.py':
        for key,value in [('title',title),('width',width),('height',height),('accent',accent)]:
            config=re.sub(r'^(\s*'+key+r'\s*:\s*[^=]+?=\s*).*$','\\g<1>'+repr(value),config,flags=re.M)
    else:
        for key,value in [('TITLE',title),('WIDTH',width),('HEIGHT',height),('ACCENT',accent)]:
            config=re.sub(r'^'+key+r'\s*=.*$',key+' = '+repr(value),config,flags=re.M)
    ui=project.files['ui/main_window.py']
    ui=re.sub(r'(tk\.Button\([^\n]*?text\s*=\s*)([\'\"][^\'\"]*[\'\"])',lambda m:m.group(1)+repr(button_text),ui,count=1)
    ui=re.sub(r'(tk\.Label\([^\n]*?text\s*=\s*)([\'\"][^\'\"]*[\'\"])',lambda m:m.group(1)+repr(label_text),ui,count=1)
    ast.parse(config);ast.parse(ui)
    project.update(config_name,config);project.update('ui/main_window.py',ui)
    return preview_settings(project.files)

def check_project(files):
    problems=[]
    for name,code in files.items():
        if name.endswith('.py'):
            try: ast.parse(code,filename=name)
            except SyntaxError as exc: problems.append(f'{name}:{exc.lineno}: {exc.msg}')
    for name in ('main.py','app/application.py','api/task_api.py','models/task.py','services/task_service.py','data/task_repository.py','ui/main_window.py','settings.py','tests/test_service.py'):
        if name not in files: problems.append('Отсутствует '+name)
    return problems

class Workspace:
    """In-memory edits only; explicit export never overwrites existing files."""
    def __init__(self): self.project=GuidedProject();self.active='main.py'
    def select(self,name):
        if name not in self.project.files: raise KeyError(name)
        self.active=name;return self.project.files[name]
    def save(self,code): self.project.update(self.active,code)
    def export(self,folder): return self.project.export(folder)

EXPLAIN_FALLBACK=line_explanation
