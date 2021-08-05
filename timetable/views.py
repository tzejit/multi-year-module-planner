import ast
from django.http.response import HttpResponseRedirect
from django.shortcuts import render
from django.db import models
import requests
from django import forms
from django.urls import reverse
import logging

'''
sessions
keyed by code [sem number, prereq if applicable, mods it is prereq for]
keyed by sem [mods taken in sem]

'''
MOD_PREREQ = []
def prereqrec(tree, type ,snum, request, code):
  global MOD_PREREQ
  if type == None:
    for i in tree: 
      if i == "and" or i == "or":
        return prereqrec(tree[i], i, snum, request, code)
      elif tree in request.session and request.session[tree][0] < snum:
        MOD_PREREQ += [tree]
        return (True, None, None)
      else:
        return (False, tree, "module")
  elif type == "or":
    for i in tree: 
      if not i == "and" and not isinstance(i,dict):
        if i in request.session and request.session[i][0] < snum:
          MOD_PREREQ += [i]
          return (True, None, None)
      else:
        if prereqrec(i, "and", snum, request, code)[0]:
          return (True, None)
    while isinstance(tree,dict):
      tree = tree.values()
    return (False, tree, "either")
  else:
    for i in tree: 
      if not i == "or" and not isinstance(i,dict):
        if i not in request.session or request.session[i][0] >= snum:
          return (False,i,"all of")
        else:
          MOD_PREREQ += [i]
      else:
        a = prereqrec(i, "or", snum, request, code)
        if not a[0]:
          return a
    return (True,None, None)
'''        
def checkprereqrec(tree, type ,snum, request):
  if type == None:
    for i in tree: 
      if i == "and" or i == "or":
        return checkprereqrec(tree[i], i, snum, request)
      elif tree in request.session and request.session[tree][0] < snum:
        return True
      else:
        return False
  elif type == "or":
    for i in tree: 
      if not i == "and" and not isinstance(i,dict):
       if i in request.session and request.session[i][0] < snum:
        return True
      else:
        return checkprereqrec(i, "and", snum, request)
    return False
  else:
    for i in tree: 
      if not i == "or" and not isinstance(i,dict):
        if i not in request.session or request.session[i][0] >= snum:
          return False
      else:
        if not prereqrec(i, "or", snum, request):
          return prereqrec(i, "or", snum, request)
    return True
''' 
    

logger = logging.getLogger(__name__)
class Module(models.Model):
    code = models.CharField(max_length=9)
    name = models.CharField(max_length=64)
    semester = models.IntegerField()
    def __str__(self):
      return f"{self.code}: {self.name}"

MOD_LIST = []
def index(request):
  ALL_MODS_TAKEN = request.session["ALL_MODS_TAKEN"]
  MOD_PRMODS = request.session["MOD_PRMODS"]
  MOD_ISPR = request.session["MOD_ISPR"]
  global MOD_PREREQ
  modarr = []
  if request.method == "POST":  
    if request.POST.get("count"): # count is num of sems planning for
      i = request.POST.get("count")
      request.session["req"] = []
      request.session["count"] = int(i)
      for j in range(int(i)):
        request.session[str(j+1)] = []
        modarr += [request.session[str(j+1)]]
      return render(request, "timetable/index.html", {
        "range" : modarr,
        "form": ModForm(),
        "num": Counter(),
        "req" : request.session["req"],
        "modstaken" : ALL_MODS_TAKEN
        })
    elif request.POST.get("rmbtn"): #remove
      d = ast.literal_eval(request.POST.get("rmbtn"))
      c = d["code"]
      if c in MOD_ISPR:
        mlist = MOD_ISPR[c]
      else:
        mlist = False
      if mlist:
        for j in range(request.session["count"]):
          modarr += [request.session[str(j+1)]]
        return render(request, "timetable/index.html", {
          "range" : modarr,
          "form": ModForm(),
          "del": True,
          "mod": mlist,
          "nm" : c,
          "num": Counter(),
          "req" : request.session["req"],
          "modstaken" : ALL_MODS_TAKEN
          })
      if c in MOD_PRMODS:
        for j in MOD_PRMODS[c]:
          MOD_ISPR[j].remove(c)
      request.session[request.POST.get("snum")].remove(d)
      del request.session[c]
      ALL_MODS_TAKEN.remove(c)
      if c in MOD_ISPR:
        del MOD_ISPR[c]
      request.session.modified = True
      return HttpResponseRedirect(reverse("mods:index"))
    elif request.POST.get("rmreq"): #remove grad req
      request.session["req"].remove(request.POST.get("rmreq"))
      request.session.modified = True
      return HttpResponseRedirect(reverse("mods:index"))
    elif request.POST.get("addreq"): #add grad req
      d = ast.literal_eval(request.POST.get("modsel"))
      c = d["code"]
      if c not in request.session["req"]:
        request.session["req"] += [c]
        return HttpResponseRedirect(reverse("mods:index"))
      else: 
        for j in range(request.session["count"]):
          modarr += [request.session[str(j+1)]]
        return render(request, "timetable/index.html", {
          "range" : modarr,
          "form": ModForm(),
          "repeat": True,
          "num": Counter(),
          "req" : request.session["req"],
          "modstaken" : ALL_MODS_TAKEN
          })
    else:   #add
      d = ast.literal_eval(request.POST.get("modsel"))
      c = d["code"]
      link = 'https://api.nusmods.com/v2/2019-2020/modules/'+ c +'.json'
      if c not in request.session:
        response = requests.get(link)
        modlist = response.json()
        d["mc"] = modlist["moduleCredit"]
        if "prereqTree" not in modlist:
          request.session[request.POST.get("snum")] += [d]
          ALL_MODS_TAKEN += [c]
          request.session[c] = [request.POST.get("snum"),None]
          request.session.modified = True
          return HttpResponseRedirect(reverse("mods:index"))
        MOD_PREREQ = []
        tup = prereqrec(modlist["prereqTree"], None, request.POST.get("snum"),request,c)
        if tup[0]:
          request.session[request.POST.get("snum")] += [d]
          ALL_MODS_TAKEN += [c]
          request.session[c] = [request.POST.get("snum"),modlist["prereqTree"]]
          MOD_PRMODS[c] = []
          for m in MOD_PREREQ:
            MOD_PRMODS[c] += [m]
            if m not in request.session["MOD_ISPR"]:
              MOD_ISPR[m] = []
            MOD_ISPR[m] += [c]
          request.session.modified = True
          return HttpResponseRedirect(reverse("mods:index"))
        else:
          for j in range(request.session["count"]):
            modarr += [request.session[str(j+1)]]
          return render(request, "timetable/index.html", {
          "range" : modarr, #range(1,request.session["count"]+1),
          "form": ModForm(),
          "prereq": True,
          "md": tup[1],
          "type": tup[2],
          "num": Counter(),
          "req" : request.session["req"],
          "modstaken" : ALL_MODS_TAKEN
          })
      for j in range(request.session["count"]):
        modarr += [request.session[str(j+1)]]
      return render(request, "timetable/index.html", {
      "range" : modarr,
      "form": ModForm(),
      "repeat": True,
      "num": Counter(),
      "req" : request.session["req"],
      "modstaken" : ALL_MODS_TAKEN
      })
  else:
    if "count" not in request.session:
      modarr = []
      request.session["ALL_MODS_TAKEN"] = []
      request.session["MOD_PRMODS"] = {} # mods to its prereq taken
      request.session["MOD_ISPR"] = {} # mods to mods that it is prereq for
      return render(request, "timetable/index_count.html")
    for j in range(request.session["count"]):
        modarr += [request.session[str(j+1)]]
    return render(request, "timetable/index.html", {
      "range" : modarr,
      "form": ModForm(),        
      "num": Counter(),
      "req" : request.session["req"],
      "modstaken" : ALL_MODS_TAKEN
      })

class ModForm(forms.Form):
    response = requests.get('https://api.nusmods.com/v2/2019-2020/moduleList.json')
    modlist = response.json()
    for mod in modlist:
      MOD_LIST.append(({"code":mod["moduleCode"]},mod["moduleCode"]))
    modsel= forms.CharField(label='Module Code', widget=forms.Select(choices=MOD_LIST))

class Counter:
    count = 1
    def inc(self):
      self.count += 1
      return " "