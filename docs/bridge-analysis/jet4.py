# Minimal read-only Jet4 (.mdb / .bws) reader - tables and rows, common column types.
import struct, sys, datetime

PS = 4096

class Jet4:
    def __init__(self, path):
        self.d = open(path, "rb").read()
        self.np = len(self.d) // PS
        self.tdefs = {}
        for p in range(self.np):
            if self.page(p)[0] == 2 and self.page(p)[1] == 1:
                try:
                    self.tdefs[p] = self.read_tdef(p)
                except Exception as e:
                    pass

    def page(self, p):
        return self.d[p * PS:(p + 1) * PS]

    def read_tdef(self, p):
        buf = bytearray(self.page(p))
        nxt = struct.unpack_from("<I", buf, 4)[0]
        seen = {p}
        while nxt and nxt not in seen and nxt < self.np:
            seen.add(nxt)
            pg = self.page(nxt)
            buf += pg[8:]
            nxt = struct.unpack_from("<I", pg, 4)[0]
        num_rows = struct.unpack_from("<I", buf, 16)[0]
        num_var = struct.unpack_from("<H", buf, 43)[0]
        num_cols = struct.unpack_from("<H", buf, 45)[0]
        num_idx = struct.unpack_from("<I", buf, 47)[0]
        num_ridx = struct.unpack_from("<I", buf, 51)[0]
        off = 63 + num_ridx * 12
        cols = []
        for i in range(num_cols):
            e = buf[off + i * 25: off + (i + 1) * 25]
            cols.append(dict(type=e[0], num=struct.unpack_from("<H", e, 5)[0],
                             var=struct.unpack_from("<H", e, 7)[0],
                             flags=e[15], fixed_off=struct.unpack_from("<H", e, 21)[0],
                             size=struct.unpack_from("<H", e, 23)[0]))
        off += num_cols * 25
        for c in cols:
            n = struct.unpack_from("<H", buf, off)[0]
            c["name"] = bytes(buf[off + 2: off + 2 + n]).decode("utf-16-le", "replace")
            off += 2 + n
        return dict(cols=cols, num_rows=num_rows)

    def text(self, b):
        if len(b) >= 2 and b[0] == 0xFF and b[1] == 0xFE:
            out, comp, i = [], True, 2
            while i < len(b):
                if b[i] == 0:
                    comp = not comp; i += 1; continue
                if comp:
                    out.append(chr(b[i])); i += 1
                else:
                    if i + 1 < len(b):
                        out.append(b[i:i + 2].decode("utf-16-le", "replace"))
                    i += 2
            return "".join(out)
        return bytes(b).decode("utf-16-le", "replace")

    def memo(self, b):
        if len(b) < 12:
            return None
        ln = struct.unpack_from("<I", b, 0)[0]
        flag, ln = ln & 0xC0000000, ln & 0x3FFFFFFF
        if flag & 0x80000000:
            return self.text(b[12:12 + ln])
        ptr = struct.unpack_from("<I", b, 4)[0]
        row, pg = ptr & 0xFF, ptr >> 8
        data = self.row_bytes(pg, row)
        if data is None:
            return None
        if flag & 0x40000000:
            return self.text(data[:ln])
        out = bytearray()
        while True:
            nxt = struct.unpack_from("<I", data, 0)[0]
            out += data[4:]
            if not nxt:
                break
            data = self.row_bytes(nxt >> 8, nxt & 0xFF)
            if data is None:
                break
        return self.text(bytes(out[:ln]))

    def row_bytes(self, p, r):
        pg = self.page(p)
        n = struct.unpack_from("<H", pg, 12)[0]
        if r >= n:
            return None
        start = struct.unpack_from("<H", pg, 14 + 2 * r)[0] & 0x1FFF
        end = PS if r == 0 else struct.unpack_from("<H", pg, 14 + 2 * (r - 1))[0] & 0x1FFF
        return pg[start:end]

    def rows(self, name):
        tp = [p for p, t in self.tdefs.items() if self.table_name(p) == name]
        out = []
        for tdp in tp:
            t = self.tdefs[tdp]
            for p in range(self.np):
                pg = self.page(p)
                if pg[0] != 1 or struct.unpack_from("<I", pg, 4)[0] != tdp:
                    continue
                n = struct.unpack_from("<H", pg, 12)[0]
                for r in range(n):
                    o = struct.unpack_from("<H", pg, 14 + 2 * r)[0]
                    if o & 0x8000:
                        continue  # deleted
                    data = self.row_bytes(p, r)
                    if o & 0x4000:  # overflow pointer
                        ptr = struct.unpack_from("<I", data, 0)[0]
                        data = self.row_bytes(ptr >> 8, ptr & 0xFF)
                    try:
                        out.append(self.parse_row(t, data))
                    except Exception as e:
                        out.append({"_error": str(e)})
        return out

    def parse_row(self, t, b):
        cols = t["cols"]
        ncols = struct.unpack_from("<H", b, 0)[0]
        bm = (ncols + 7) // 8
        mask = b[len(b) - bm:]
        def present(cn):
            return cn < ncols and (mask[cn // 8] >> (cn % 8)) & 1
        nvar = struct.unpack_from("<H", b, len(b) - bm - 2)[0]
        voffs = [struct.unpack_from("<H", b, len(b) - bm - 4 - 2 * i)[0] for i in range(nvar + 1)]
        rec = {}
        for c in cols:
            cn, ty = c["num"], c["type"]
            if ty == 1:
                rec[c["name"]] = bool(present(cn)); continue
            if not present(cn):
                rec[c["name"]] = None; continue
            if c["flags"] & 1:  # fixed
                s = 2 + c["fixed_off"]
                raw = b[s:s + c["size"]]
            else:
                vi = c["var"]
                if vi >= nvar:
                    rec[c["name"]] = None; continue
                raw = b[voffs[vi]:voffs[vi + 1]]
            rec[c["name"]] = self.conv(ty, raw)
        return rec

    def conv(self, ty, raw):
        if ty == 2: return raw[0]
        if ty == 3: return struct.unpack("<h", raw[:2])[0]
        if ty == 4: return struct.unpack("<i", raw[:4])[0]
        if ty == 5: return struct.unpack("<q", raw[:8])[0] / 10000
        if ty == 6: return struct.unpack("<f", raw[:4])[0]
        if ty == 7: return struct.unpack("<d", raw[:8])[0]
        if ty == 8:
            v = struct.unpack("<d", raw[:8])[0]
            return datetime.datetime(1899, 12, 30) + datetime.timedelta(days=v)
        if ty == 10: return self.text(raw)
        if ty == 12: return self.memo(raw)
        return raw.hex()

    def table_name(self, tdp):
        return self._names().get(tdp)

    def _names(self):
        if hasattr(self, "_nm"):
            return self._nm
        self._nm = {}
        for p, t in self.tdefs.items():
            if any(c["name"] == "Name" for c in t["cols"]) and any(c["name"] == "Id" for c in t["cols"]) \
                    and any(c["name"] == "Type" for c in t["cols"]):
                sys_tdp = p
                break
        else:
            return self._nm
        self._nm[sys_tdp] = "MSysObjects"
        for r in self.rows_raw(sys_tdp):
            if r.get("Type") in (1,) and r.get("Id") is not None:
                self._nm[r["Id"] & 0x00FFFFFF] = r["Name"]
        return self._nm

    def rows_raw(self, tdp):
        t = self.tdefs[tdp]; out = []
        for p in range(self.np):
            pg = self.page(p)
            if pg[0] != 1 or struct.unpack_from("<I", pg, 4)[0] != tdp:
                continue
            n = struct.unpack_from("<H", pg, 12)[0]
            for r in range(n):
                o = struct.unpack_from("<H", pg, 14 + 2 * r)[0]
                if o & 0xC000:
                    continue
                try:
                    out.append(self.parse_row(t, self.row_bytes(p, r)))
                except Exception:
                    pass
        return out
