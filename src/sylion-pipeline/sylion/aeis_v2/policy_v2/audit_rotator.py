from datetime import datetime, timedelta
from pathlib import Path


class W19AuditRotator:
    @classmethod
    def rotate_if_size_exceeds(cls, path, max_mb=50):
        p = Path(path)
        if not p.exists() or p.stat().st_size <= max_mb * 1024 * 1024:
            return None
        d = datetime.now().strftime("%Y-%m-%d")
        n = 1
        while True:
            target = p.with_name(f"{p.name}.{d}.{n}.jsonl")
            if not target.exists():
                p.rename(target)
                return target
            n += 1

    @classmethod
    def collect_old(cls, path, keep_days=30):
        p, cut, dead = Path(path), datetime.now().date() - timedelta(days=keep_days), []
        for f in p.parent.glob(f"{p.name}.*.jsonl"):
            s = f.name[len(p.name) + 1 : -6]
            try:
                if datetime.strptime(s.rsplit(".", 1)[0], "%Y-%m-%d").date() < cut:
                    f.unlink(); dead.append(f)
            except ValueError:
                pass
        return dead
