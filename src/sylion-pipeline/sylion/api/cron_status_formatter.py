class CronStatusFormatter:
    @staticmethod
    def format_status(status_dict: dict) -> str:
        headers = ["Total Commits", "Recent", "Drafts KB"]
        values = [
            str(status_dict.get("total_commits", 0)),
            str(len(status_dict.get("recent_commits", []) or [])),
            str(status_dict.get("drafts_size_kb", 0)),
        ]
        widths = [max(len(h), len(v)) for h, v in zip(headers, values)]
        fmt = " | ".join(f"{{:<{w}}}" for w in widths)
        rows = (headers, ["-" * w for w in widths], values)
        return "\n".join(fmt.format(*row).rstrip() for row in rows)
