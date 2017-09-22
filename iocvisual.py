#!/usr/bin/env python
# -*- coding: utf-8 -*-

import xmltodict

from pprint import pprint
import collections
import random
import string
import errno
import json
import copy
import sys
import os


# https://stackoverflow.com/a/16029908/1079836
def mkdirp(path):
  if path and path != "":
    try:
      os.makedirs(path)
    except OSError as exc:
      if exc.errno == errno.EEXIST and os.path.isdir(path):
        pass
      else:
        raise

# https://stackoverflow.com/a/44858562/1079836
class stack:
  def __init__(self):
    self.items=[]
  def isEmpty(self):
    return self.items==[]
  def push(self, item):
    self.items.append(item)
  def pop(self):
    return self.items.pop()
  def size(self):
    return len(self.items)
  def peek(self):
    return self.items[-1]
  def show(self):
    return self.items


class iocvisual:
  def __init__(self, filepath):
    if os.path.isfile(filepath):
      self.filepath = filepath
      self.verbose = True
      self.isqlysioc = True
      self.groupchildren = True
      self.collapsecount = 25
      self.saveiocdict = True
      self.content = None
      self.iocdict = None
      self.d3dict = None
      self.error = None
      self.basereportsdir = "%s/reports" % (os.getcwd())
      self.currentreportsdir = "%s/%s" % (self.basereportsdir, self.filepath.split("/")[-1])
      mkdirp(self.currentreportsdir)
      self.iocjsonpath = "%s/ioc.json" % (self.currentreportsdir)
      self.iocd3jsonpath = "%s/iocd3.json" % (self.currentreportsdir)
      self.htmlplainpath = "%s/iocplain.html" % (self.currentreportsdir)
      self.htmlzoompath = "%s/ioczoom.html" % (self.currentreportsdir)
      self.operators = stack()
      self.opids = stack()
      self.ignorelist = [
        "@id",
        "@condition",
        "@preserve-case",
        "@negate",
        "@xmlns:xsi",
        "@xmlns:xsd",
        "@document",
        "@type",
        "@operator"
      ]
    else:
      self.error = "no such file: %s" % (filepath)

  def ioc_to_dict(self):
    with open(self.filepath) as fo:
      self.content = fo.read()
      try:
        self.iocdict = xmltodict.parse(self.content)
      except:
        return self
    if self.iocdict and self.saveiocdict:
      with open(self.iocjsonpath, "w") as fo:
        json.dump(self.iocdict, fo)
    return self

  def create_tree(self, intree, outtree, grouptree):
    if isinstance(intree, collections.OrderedDict):
      for key, value in dict(intree).iteritems():
        if key == "Indicator":
          # for indicator, extract operator
          if isinstance(value, collections.OrderedDict):
            self.operators.push(dict(value)["@operator"])
            try:
              self.opids.push(dict(value)["@id"])
            except:
              continue
            tmpnode = dict({
              "name": "%s_%s" % (self.operators.peek(), self.opids.peek().split("-")[0]),
              "children": list()
            })
            self.create_tree(value, tmpnode["children"], tmpnode)
            self.operators.pop() ; self.opids.pop()
            outtree.append(tmpnode)
          elif isinstance(value, list):
            for item in value:
              self.operators.push(dict(item)["@operator"]) ; self.opids.push(dict(item)["@id"])
              tmpnode = dict({
                "name": "%s_%s" % (self.operators.peek(), self.opids.peek().split("-")[0]),
                "children": list()
              })
              self.create_tree(item, tmpnode["children"], tmpnode)
              self.operators.pop() ; self.opids.pop()
              outtree.append(tmpnode)
        elif key == "IndicatorItem":
          #for indicatoritem, extract search and text from context and content resp.
          if isinstance(value, list):
            grouptree["name"] = "%s (%d)" % (grouptree["name"], len(value))
            if self.groupchildren and self.isqlysioc:
              try:
                search = dict(dict(value[0])["Context"])["@search"]
                if "RegistryItem" in search:
                  reglist = []
                  for item in value:
                    try: reglist.append(dict(dict(item)["Content"])["#text"])
                    except: continue
                  grouptree["name"] = "RegistryItem: %s" % ("\\".join(reglist))
                  del grouptree["children"]
                elif "FileItem" in search and "FileItem/Sha256sum" not in search:
                  filelist = []
                  for item in value:
                    try: filelist.append(dict(dict(item)["Content"])["#text"])
                    except: continue
                  grouptree["name"] = "FileItem: %s" % ("\\".join(filelist))
                  del grouptree["children"]
                else:
                  if len(value) > self.collapsecount:
                    del grouptree["children"]
                    grouptree["_children"] = []
                    outtree = grouptree["_children"]
                  for item in value:
                    try:
                      search = dict(dict(item)["Context"])["@search"]
                    except:
                      search = None
                      if self.verbose:
                        print "context-search not found in %s" % (self.filepath)
                      continue
                    try:
                      text = dict(dict(item)["Content"])["#text"]
                    except:
                      text = None
                      if self.verbose:
                        print "content-text not found in %s" % (self.filepath)
                      continue
                    outtree.append({
                      "name": "%s: %s" % (search, text)
                    })
              except:
                pass
            else:
              for item in value:
                try:
                  search = dict(dict(item)["Context"])["@search"]
                except:
                  search = None
                  if self.verbose:
                    print "context-search not found in %s" % (self.filepath)
                  continue
                try:
                  text = dict(dict(item)["Content"])["#text"]
                except:
                  text = None
                  if self.verbose:
                    print "content-text not found in %s" % (self.filepath)
                  continue
                outtree.append({
                  "name": "%s: %s" % (search, text)
                })
        else:
          if isinstance(value, collections.OrderedDict):
            tmpnode = dict({
              "name": key,
              "children": list()
            })
            self.create_tree(value, tmpnode["children"], tmpnode)
            outtree.append(tmpnode)
          elif isinstance(value, list):
            for item in value:
              tmpnode = dict({
                "name": key,
                "children": list()
              })
              self.create_tree(item, tmpnode["children"], tmpnode)
              outtree.append(tmpnode)
          else:
            if key not in self.ignorelist:
              outtree.append({
                "name": "%s: %s" % (key, value)
              })
    return self

  def dict_to_d3(self):
    if self.iocdict:
      try:
        self.d3dict = dict({
          "name": "ROOT",
          "children": list()
        })

        self.isqlysioc = True if "qualys_ioc_envelop" in self.iocdict else False

        self.create_tree(self.iocdict, self.d3dict["children"], self.d3dict)

        if self.d3dict:
          with open(self.iocd3jsonpath, "w") as fo:
            json.dump(self.d3dict, fo)
      except:
        import traceback
        traceback.print_exc()
    return self

  def create_html(self):
    htmlplaincontent = """<!DOCTYPE html><meta charset=utf-8><style>.node{cursor:pointer}.node circle{fill:#fff;stroke:#4682b4;stroke-width:3px}.node text{font:15px sans-serif}.link{fill:none;stroke:#ccc;stroke-width:1.5px}div#container{height:100%;width:100%;border:2px solid #000;overflow:scroll;}</style><body><script src=../../d3/d3.v3.min.js></script><script>function update(t){var r=tree.nodes(root).reverse(),n=tree.links(r);r.forEach(function(t){t.y=180*t.depth});var e=svg.selectAll("g.node").data(r,function(t){return t.id||(t.id=++i)}),a=e.enter().append("g").attr("class","node").attr("transform",function(r){return"translate("+t.y0+","+t.x0+")"}).on("click",click);a.append("circle").attr("r",1e-6).style("fill",function(t){return t._children?"lightsteelblue":"#fff"}),a.append("text").attr("x",function(t){return t.children||t._children?-10:10}).attr("dy",".35em").attr("text-anchor",function(t){return t.children||t._children?"end":"start"}).text(function(t){return t.name}).style("fill-opacity",1e-6);var o=e.transition().duration(duration).attr("transform",function(t){return"translate("+t.y+","+t.x+")"});o.select("circle").attr("r",6).style("fill",function(t){return t._children?"lightsteelblue":"#fff"}),o.select("text").style("fill-opacity",1);var l=e.exit().transition().duration(duration).attr("transform",function(r){return"translate("+t.y+","+t.x+")"}).remove();l.select("circle").attr("r",1e-6),l.select("text").style("fill-opacity",1e-6);var c=svg.selectAll("path.link").data(n,function(t){return t.target.id});c.enter().insert("path","g").attr("class","link").attr("d",function(r){var n={x:t.x0,y:t.y0};return diagonal({source:n,target:n})}),c.transition().duration(duration).attr("d",diagonal),c.exit().transition().duration(duration).attr("d",function(r){var n={x:t.x,y:t.y};return diagonal({source:n,target:n})}).remove(),r.forEach(function(t){t.x0=t.x,t.y0=t.y})}function click(t){t.children?(t._children=t.children,t.children=null):(t.children=t._children,t._children=null),update(t)}var margin={top:20,right:120,bottom:20,left:120},width=4e3-margin.right-margin.left,height=700-margin.top-margin.bottom,i=0,duration=750,root,tree=d3.layout.tree().size([height,width]),diagonal=d3.svg.diagonal().projection(function(t){return[t.y,t.x]}),container=d3.select("body").append("div").attr("id","container"),svg=container.append("svg").attr("width",width+margin.right+margin.left).attr("height",height+margin.top+margin.bottom).append("g").attr("transform","translate("+margin.left+","+margin.top+")");d3.json("iocd3.json",function(t,r){function n(t){t.children&&(t._children=t.children,t._children.forEach(n),t.children=null)}if(t)throw t;(root=r).x0=height/2,root.y0=0,root.children.forEach(n),update(root)}),d3.select(self.frameElement).style("height","800px")</script>"""
    htmlzoomcontent = """<!DOCTYPE html><meta charset="utf-8"><style type="text/css">.node{cursor: pointer;}.overlay{background-color: #EEE;}.node circle{fill: #fff; stroke: steelblue; stroke-width: 2px;}.node text{font-size: 10px; font-weight: bold; font-family: "courier new";}.link{fill: none; stroke: #ccc; stroke-width: 1.5px;}.templink{fill: none; stroke: red; stroke-width: 3px;}.ghostCircle.show{display: block;}.ghostCircle, .activeDrag .ghostCircle{display: none;}</style><script src="../../assets/jquery-1.10.2.min.js"></script><script src="../../assets/d3.v3.min.js"></script><script src="../../assets/color-hash.js"></script><script>treeJSON=d3.json("iocd3.json", function(t, e){function n(t, e, r){if (t){e(t); var a=r(t); if (a) for (var l=a.length, i=0; l > i; i++) n(a[i], e, r)}}function r(){E.sort(function(t, e){return e.name.toLowerCase() < t.name.toLowerCase() ? 1 : -1})}function a(t, e){var n=C; panTimer && (clearTimeout(panTimer), translateCoords=d3.transform(S.attr("transform")), "left"==e || "right"==e ? (translateX="left"==e ? translateCoords.translate[0] + n : translateCoords.translate[0] - n, translateY=translateCoords.translate[1]) : ("up"==e || "down"==e) && (translateX=translateCoords.translate[0], translateY="up"==e ? translateCoords.translate[1] + n : translateCoords.translate[1] - n), scaleX=translateCoords.scale[0], scaleY=translateCoords.scale[1], scale=X.scale(), S.transition().attr("transform", "translate(" + translateX + "," + translateY + ")scale(" + scale + ")"), d3.select(t).select("g.node").attr("transform", "translate(" + translateX + "," + translateY + ")"), X.scale(X.scale()), X.translate([translateX, translateY]), panTimer=setTimeout(function(){a(t, n, e)}, 50))}function l(){S.attr("transform", "translate(" + d3.event.translate + ")scale(" + d3.event.scale + ")")}function i(t, e){m=t, d3.select(e).select(".ghostCircle").attr("pointer-events", "none"), d3.selectAll(".ghostCircle").attr("class", "ghostCircle show"), d3.select(e).attr("class", "node activeDrag"), S.selectAll("g.node").sort(function(t, e){return t.id !=m.id ? 1 : -1}), nodes.length > 1 && (links=E.links(nodes), nodePaths=S.selectAll("path.link").data(links, function(t){return t.target.id}).remove(), nodesExit=S.selectAll("g.node").data(nodes, function(t){return t.id}).filter(function(t, e){return t.id==m.id ? !1 : !0}).remove()), parentLink=E.links(E.nodes(m.parent)), S.selectAll("path.link").filter(function(t, e){return t.target.id==m.id ? !0 : !1}).remove(), dragStarted=null}function o(){v=null, d3.selectAll(".ghostCircle").attr("class", "ghostCircle"), d3.select(domNode).attr("class", "node"), d3.select(domNode).select(".ghostCircle").attr("pointer-events", ""), z(), null !==m && (f(h), c(m), m=null)}function s(t){t._children && (t.children=t._children, t.children.forEach(s), t._children=null)}function c(t){scale=X.scale(), x=-t.y0, y=-t.x0, x=x * scale + A / 2, y=y * scale + w / 2, d3.select("g").transition().duration(T).attr("transform", "translate(" + x + "," + y + ")scale(" + scale + ")"), X.scale(scale), X.translate([x, y])}function d(t){return t.children ? (t._children=t.children, t.children=null) : t._children && (t.children=t._children, t._children=null), t}function u(t){d3.event.defaultPrevented || (t=d(t), f(t), c(t))}function getRandomColor(){var letters='0123456789ABCDEF'; var color='#'; for (var i=0; i < 6; i++){color +=letters[Math.floor(Math.random() * 16)];}return color;}function getRandomFloat(a, b){return (Math.random() * (b - a) + a).toFixed(4);}function f(t){var e=[1], n=function(t, r){r.children && r.children.length > 0 && (e.length <=t + 1 && e.push(0), e[t + 1] +=r.children.length, r.children.forEach(function(e){n(t + 1, e)}))}; n(0, h); var r=25 * d3.max(e); E=E.size([r, A]); var a=E.nodes(h).reverse(), l=E.links(a); a.forEach(function(t){t.y=300 * t.depth}), node=S.selectAll("g.node").data(a, function(t){return t.id || (t.id=++k)}); var i=node.enter().append("g").call(dragListener).attr("class", "node").attr("transform", function(e){return "translate(" + t.y0 + "," + t.x0 + ")"}).on("click", u); i.append("circle").attr("class", "nodeCircle").attr("r", 0).style("fill", function(t){return t._children ? "lightsteelblue" : "#fff"}), i.append("text").attr("x", function(t){return t.children || t._children ? -10 : 10}).attr("dy", ".35em").attr("class", "nodeText").attr("text-anchor", function(t){return t.children || t._children ? "end" : "start"}).text(function(t){return t.name}).style("fill-opacity", 0), i.append("circle").attr("class", "ghostCircle").attr("r", 30).attr("opacity", .2).style("fill", "red").attr("pointer-events", "mouseover").on("mouseover", function(t){L(t)}).on("mouseout", function(t){b(t)}), node.select("text").attr("x", function(t){return t.children || t._children ? -10 : 10}).attr("text-anchor", function(t){return t.children || t._children ? "end" : "start"}).text(function(t){return t.name}), node.select("circle.nodeCircle").attr("r", 4.5).style("fill", function(t){return t._children ? "white" : new ColorHash({lightness: 0.35, saturation: 0.65}).hex(t.name);}); var o=node.transition().duration(T).attr("transform", function(t){return "translate(" + t.y + "," + t.x + ")"}); o.select("text").style("fill-opacity", 1); var s=node.exit().transition().duration(T).attr("transform", function(e){return "translate(" + t.y + "," + t.x + ")"}).remove(); s.select("circle").attr("r", 0), s.select("text").style("fill-opacity", 0); var c=S.selectAll("path.link").data(l, function(t){return t.target.id}); c.enter().insert("path", "g").attr("class", "link").attr("d", function(e){var n={x: t.x0, y: t.y0}; return N({source: n, target: n})}), c.transition().duration(T).attr("d", N), c.exit().transition().duration(T).attr("d", function(e){var n={x: t.x, y: t.y}; return N({source: n, target: n})}).remove(), a.forEach(function(t){t.x0=t.x, t.y0=t.y})}var h, g=0, p=0, v=null, m=null, C=200, _=20, k=0, T=750, A=$(document).width()*0.99, w=$(document).height()*0.96, E=d3.layout.tree().size([w, A]), N=d3.svg.diagonal().projection(function(t){return [t.y, t.x]}); n(e, function(t){g++, p=Math.max(t.name.length, p)}, function(t){return t.children && t.children.length > 0 ? t.children : null}), r(); var X=d3.behavior.zoom().scaleExtent([.1, 3]).on("zoom", l), Y=d3.select("#tree-container").append("svg").attr("width", A).attr("height", w).attr("class", "overlay").call(X); dragListener=d3.behavior.drag().on("dragstart", function(t){t !=h && (dragStarted=!0, nodes=E.nodes(t), d3.event.sourceEvent.stopPropagation())}).on("drag", function(t){if (t !=h){if (dragStarted && (domNode=this, i(t, domNode)), relCoords=d3.mouse($("svg").get(0)), relCoords[0] < _) panTimer=!0, a(this, "left"); else if (relCoords[0] > $("svg").width() - _) panTimer=!0, a(this, "right"); else if (relCoords[1] < _) panTimer=!0, a(this, "up"); else if (relCoords[1] > $("svg").height() - _) panTimer=!0, a(this, "down"); else try{clearTimeout(panTimer)}catch (e){}t.x0 +=d3.event.dy, t.y0 +=d3.event.dx; var n=d3.select(this); n.attr("transform", "translate(" + t.y0 + "," + t.x0 + ")"), z()}}).on("dragend", function(t){if (t !=h) if (domNode=this, v){var e=m.parent.children.indexOf(m); e > -1 && m.parent.children.splice(e, 1), "undefined" !=typeof v.children || "undefined" !=typeof v._children ? "undefined" !=typeof v.children ? v.children.push(m) : v._children.push(m) : (v.children=[], v.children.push(m)), s(v), r(), o()}else o()}); var L=function(t){v=t, z()}, b=function(t){v=null, z()}, z=function(){var t=[]; null !==m && null !==v && (t=[{source:{x: v.y0, y: v.x0}, target:{x: m.y0, y: m.x0}}]); var e=S.selectAll(".templink").data(t); e.enter().append("path").attr("class", "templink").attr("d", d3.svg.diagonal()).attr("pointer-events", "none"), e.attr("d", d3.svg.diagonal()), e.exit().remove()}, S=Y.append("g"); h=e, h.x0=w / 2, h.y0=0, f(h), c(h)});</script><body> <div id="tree-container"></div></body></html>"""

    try:
      if self.iocdict and self.d3dict and self.htmlplainpath:
        with open(self.htmlplainpath, "w") as fo:
          fo.write(htmlplaincontent)
        with open(self.htmlzoompath, "w") as fo:
          fo.write(htmlzoomcontent)
    except:
      import traceback
      traceback.print_exc()
    return self

  def process(self):
    self.ioc_to_dict()
    self.dict_to_d3()
    self.create_html()
    return self


if __name__ == "__main__":
  if len(sys.argv) != 2:
    print "USAGE: %s <ioc.xml>" % (sys.argv[0])
    sys.exit(1)

  iv = iocvisual(sys.argv[1])
  if not iv.error:
    iv.process()
  else:
    print iv.error
