from maya import cmds


def short(n):
    return n.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


def get_ctrls(root, nurbs_only=True):
    if not root or not cmds.objExists(root):
        return []
    nodes = cmds.listRelatives(root, ad=True, type="transform", f=True) or []
    nodes.append(root)
    if nurbs_only:
        nodes = [n for n in nodes if cmds.listRelatives(n, s=True, type="nurbsCurve", f=True)]
    out = []
    for n in nodes:
        if n not in out:
            out.append(n)
    return out


# мьютим кейнутые каналы и кидаем в дефолт, чтобы соурс встал в нейтраль
def rest_pose(ctrls):
    muted = []
    for c in ctrls:
        for at in (cmds.listAttr(c, k=True) or []):
            plug = c + "." + at
            df = cmds.attributeQuery(at, node=c, listDefault=True) or []
            if not df:
                continue
            if cmds.connectionInfo(plug, isDestination=True):
                try:
                    cmds.mute(plug)
                    muted.append(plug)
                except:
                    continue
            try:
                cmds.setAttr(plug, *df)
            except:
                pass
    return muted


def unmute(muted):
    for plug in muted:
        try:
            cmds.mute(plug, disable=True, force=True)
        except:
            pass


def retarget(src_root, tgt_root, nurbs_only=True, mo=True, rest=True):
    if not (src_root and tgt_root and cmds.objExists(src_root) and cmds.objExists(tgt_root)):
        cmds.warning("нет соурса или таргета")
        return

    src = get_ctrls(src_root, nurbs_only)
    tgt = get_ctrls(tgt_root, nurbs_only)
    print("src %d / tgt %d" % (len(src), len(tgt)))
    if not src or not tgt:
        cmds.warning("контролы не нашёл")
        return

    smap = {}
    for c in src:
        smap.setdefault(short(c), c)

    muted = rest_pose(src) if rest else []

    ok, miss, skip, err = [], [], [], []
    for t in tgt:
        b = short(t)
        s = smap.get(b)
        if not s:
            miss.append(b)
            continue
        if cmds.listRelatives(t, type="parentConstraint"):
            skip.append(b)
            continue
        try:
            cmds.parentConstraint(s, t, mo=mo)
            ok.append(b)
        except Exception as e:
            err.append("%s: %s" % (b, e))

    if rest:
        unmute(muted)

    print("законстрейнено: %d" % len(ok))
    if miss:
        print("без пары: %s" % sorted(miss))
    if skip:
        print("уже с констрейном: %s" % sorted(skip))
    if err:
        print("ошибки: %s" % err)
    return ok


def kill_cons(tgt_root, nurbs_only=True):
    cons = set()
    for c in get_ctrls(tgt_root, nurbs_only):
        for con in (cmds.listConnections(c, type="constraint") or []):
            cons.add(con)
    cons = [c for c in cons if cmds.objExists(c)]
    if cons:
        cmds.delete(cons)
    print("снято констрейнов: %d" % len(cons))
    return cons


def bake(tgt_root, nurbs_only=True, start=None, end=None):
    ctrls = get_ctrls(tgt_root, nurbs_only)
    if not ctrls:
        cmds.warning("нет контролов на таргете")
        return
    if start is None:
        start = cmds.playbackOptions(q=True, min=True)
    if end is None:
        end = cmds.playbackOptions(q=True, max=True)
    cmds.bakeResults(ctrls, simulation=True, t=(start, end), sampleBy=1,
                     preserveOutsideKeys=True, disableImplicitControl=True)
    kill_cons(tgt_root, nurbs_only)
    print("запёк %d-%d" % (int(start), int(end)))


# ---- окно ----

class RetargetTool(object):
    win = "retargetToolWin"

    def __init__(self):
        self.src = None
        self.tgt = None

    def build(self):
        if cmds.window(self.win, ex=True):
            cmds.deleteUI(self.win)
        cmds.window(self.win, t="Retarget", wh=(330, 310), s=True)
        cmds.columnLayout(adj=True, rs=6, co=("both", 10))
        cmds.text(l="")
        cmds.text(l="выдели соурс-группу", al="left")
        self.f_src = cmds.textFieldButtonGrp(l="src", bl="set", cw3=(40, 190, 50),
                                             ed=False, bc=self.set_src)
        cmds.text(l="выдели таргет-группу", al="left")
        self.f_tgt = cmds.textFieldButtonGrp(l="tgt", bl="set", cw3=(40, 190, 50),
                                             ed=False, bc=self.set_tgt)
        cmds.separator(h=8, st="in")
        self.c_nurbs = cmds.checkBox(l="только nurbs", v=True)
        self.c_rest = cmds.checkBox(l="соурс в рест перед констрейном", v=True)
        self.c_mo = cmds.checkBox(l="maintain offset", v=True)
        cmds.separator(h=8, st="in")
        cmds.button(l="RETARGET", h=36, bgc=(0.34, 0.52, 0.34), c=self.run)
        cmds.rowLayout(nc=2, cw2=(150, 150))
        cmds.button(l="bake & clean", w=150, c=self.do_bake)
        cmds.button(l="снять констрейны", w=150, c=self.do_kill)
        cmds.setParent("..")
        cmds.showWindow(self.win)

    def set_src(self, *a):
        sel = cmds.ls(sl=True, l=True)
        if sel:
            self.src = sel[0]
            cmds.textFieldButtonGrp(self.f_src, e=True, tx=sel[0].rsplit("|", 1)[-1])

    def set_tgt(self, *a):
        sel = cmds.ls(sl=True, l=True)
        if sel:
            self.tgt = sel[0]
            cmds.textFieldButtonGrp(self.f_tgt, e=True, tx=sel[0].rsplit("|", 1)[-1])

    def opts(self):
        return (cmds.checkBox(self.c_nurbs, q=True, v=True),
                cmds.checkBox(self.c_mo, q=True, v=True),
                cmds.checkBox(self.c_rest, q=True, v=True))

    def run(self, *a):
        n, mo, r = self.opts()
        retarget(self.src, self.tgt, n, mo, r)

    def do_bake(self, *a):
        n, _, _ = self.opts()
        bake(self.tgt, n)

    def do_kill(self, *a):
        n, _, _ = self.opts()
        kill_cons(self.tgt, n)


RetargetTool().build()