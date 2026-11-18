"""Desktop UI for Instruction Generator AI."""
from __future__ import annotations
import json, threading, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from services.settings_service import get_theme
from .instruction_generator_core import generate_instruction, to_html, to_markdown, to_pdf

class InstructionGeneratorWindow:
    def __init__(self, parent):
        self.parent=parent; self.theme=get_theme(); self.steps=[]; self.result=None
        self.win=tk.Toplevel(parent); self.win.title("Instruction Generator AI"); self.win.geometry("1180x800"); self.win.minsize(920,650); self.win.configure(bg=self.theme["bg"])
        self._build(); self.add_step()
    def _build(self):
        top=tk.Frame(self.win,bg=self.theme["card"]); top.pack(fill="x",padx=16,pady=16)
        tk.Label(top,text="Instruction Generator AI",font=("Segoe UI",20,"bold"),bg=self.theme["card"],fg=self.theme["text"]).pack(side="left",padx=16,pady=16)
        self.status=tk.Label(top,text="Черновик",bg=self.theme["card"],fg=self.theme["gray"]); self.status.pack(side="right",padx=16)
        meta=tk.Frame(self.win,bg=self.theme["card"]); meta.pack(fill="x",padx=16,pady=(0,10))
        rule_text = "Единый формат 16,5 × 7,9 см: загружайте любые скриншоты — система автоматически находит выделенные элементы (красные рамки и маркеры), увеличивает их для идеальной читаемости и формирует все рисунки в аккуратном едином размере."
        tk.Label(meta,text=rule_text,font=("Segoe UI",9,"italic"),bg="#FEF9C3",fg="#854D0E",wraplength=880,justify="left",padx=10,pady=6).grid(row=0,column=0,sticky="ew",padx=12,pady=(6,4))
        self.title=self._field(meta,"Название инструкции",1,0); meta.columnconfigure(0,weight=1)
        host=tk.Frame(self.win,bg=self.theme["bg"]); host.pack(fill="both",expand=True,padx=16)
        self.canvas=tk.Canvas(host,bg=self.theme["bg"],highlightthickness=0); sb=tk.Scrollbar(host,command=self.canvas.yview); self.inner=tk.Frame(self.canvas,bg=self.theme["bg"])
        self.canvas.create_window((0,0),window=self.inner,anchor="nw"); self.canvas.configure(yscrollcommand=sb.set); self.inner.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all"))); self.canvas.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        actions=tk.Frame(self.win,bg=self.theme["bg"]); actions.pack(fill="x",padx=16,pady=14)
        for text,cmd,color in (("+ Добавить шаг",self.add_step,"#183153"),("Сгенерировать",self.generate,"#009246"),("PDF",lambda:self.export("pdf"),"#CE2B37"),("HTML",lambda:self.export("html"),"#183153"),("Markdown",lambda:self.export("md"),"#183153")):
            tk.Button(actions,text=text,command=cmd,bg=color,fg="white",relief="flat",padx=14,pady=9).pack(side="left",padx=(0,8))
    def _field(self,parent,label,row,col):
        tk.Label(parent,text=label,bg=self.theme["card"],fg=self.theme["text"]).grid(row=row*2,column=col,sticky="w",padx=12,pady=(8,2)); e=tk.Entry(parent); e.grid(row=row*2+1,column=col,sticky="ew",padx=12,pady=(0,8)); return e
    def add_step(self):
        card=tk.Frame(self.inner,bg=self.theme["card"],highlightthickness=1,highlightbackground="#D9E2DC"); card.pack(fill="x",pady=6)
        head=tk.Frame(card,bg=self.theme["card"]); head.pack(fill="x",padx=12,pady=(10,4)); label=tk.Label(head,text=f"Шаг {len(self.steps)+1}",font=("Segoe UI",11,"bold"),bg=self.theme["card"],fg=self.theme["text"]); label.pack(side="left")
        text=tk.Text(card,height=4,wrap="word"); text.pack(fill="x",padx=12,pady=5); caption=tk.Entry(card); caption.insert(0,"Подпись к изображению"); caption.pack(fill="x",padx=12,pady=5)
        image=tk.StringVar(); image_label=tk.Label(card,text="Скриншот не выбран",bg=self.theme["card"],fg=self.theme["gray"]); image_label.pack(side="left",padx=12,pady=10)
        def choose():
            p=filedialog.askopenfilename(filetypes=[("Изображения","*.png *.jpg *.jpeg *.webp")]);
            if p: image.set(p); image_label.configure(text=Path(p).name)
        tk.Button(card,text="Выбрать скриншот",command=choose).pack(side="right",padx=12,pady=8)
        self.steps.append({"card":card,"label":label,"text":text,"caption":caption,"image":image})
    def _payload(self):
        return {"title":self.title.get(),"audience":"","department":"","intro":"","steps":[{"text":s["text"].get("1.0","end"),"caption":s["caption"].get(),"image":s["image"].get()} for s in self.steps]}
    def generate(self):
        self.status.configure(text="ИИ обрабатывает…")
        def work():
            try: self.result=generate_instruction(self._payload()); self.win.after(0,lambda:self.status.configure(text=f"Готово · {len(self.result['steps'])} шагов")); self.win.after(0,lambda:messagebox.showinfo("Instruction Generator AI","Инструкция подготовлена. Можно экспортировать."))
            except Exception as exc: self.win.after(0,lambda:messagebox.showerror("Ошибка",str(exc))); self.win.after(0,lambda:self.status.configure(text="Ошибка"))
        threading.Thread(target=work,daemon=True).start()
    def export(self,kind):
        if not self.result:
            try:self.result=generate_instruction(self._payload())
            except Exception as exc: messagebox.showerror("Ошибка",str(exc)); return
        ext={"pdf":"pdf","html":"html","md":"md"}[kind]; p=filedialog.asksaveasfilename(defaultextension="."+ext,filetypes=[(ext.upper(),"*."+ext)])
        if not p:return
        data=to_pdf(self.result) if kind=="pdf" else (to_html(self.result) if kind=="html" else to_markdown(self.result)).encode("utf-8")
        Path(p).write_bytes(data); messagebox.showinfo("Готово",f"Файл сохранён:\n{p}")

def open_instruction_generator(parent): InstructionGeneratorWindow(parent)
