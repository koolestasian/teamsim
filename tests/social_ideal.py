"""A correct reference product for the social preset's operations (a test helper).

It implements the operations of the population format's section 5: follow, block, post,
delete_post and read_feed with the audience rules, and nothing else. A pack generated for the
social preset must be passable by it; a check that this product fails is a flaw in the pack.
"""


class Ideal:
    def __init__(self):
        self.follows = set()
        self.blocks = set()
        self.posts = []

    def visible(self, post, reader):
        author, audience = post["author"], post["audience"]
        if reader == author:
            return True
        if (author, reader) in self.blocks:
            return False
        if audience == "public":
            return True
        if audience == "followers":
            return (reader, author) in self.follows
        if audience == "friends":
            return (reader, author) in self.follows and (author, reader) in self.follows
        return False

    def handle(self, message):
        if message["type"] == "hello":
            return [{"type": "ready", "v": 1, "name": "ideal", "version": "1"}]
        if message["type"] != "event":
            return []
        payload, out = message["payload"], []
        if message["kind"] == "op":
            op, args, who = payload["op"], payload.get("args", {}), payload["actor"]
            if op == "follow":
                self.follows.add((who, args["user"]))
            elif op == "block":
                self.blocks.add((who, args["user"]))
                self.follows.discard((args["user"], who))
            elif op == "post":
                self.posts.append({"id": payload["id"], "author": who, "audience": args["audience"], "text": args["text"]})
            elif op == "delete_post":
                self.posts = [p for p in self.posts if p["id"] != args["post"]]
            elif op == "read_feed":
                feed = [p["text"] for p in self.posts if self.visible(p, who)][-args["limit"] :]
                out = [
                    {
                        "type": "action",
                        "in_reply_to": message["seq"],
                        "kind": "result",
                        "surface": payload["surface"],
                        "text": " | ".join(feed) or "empty",
                        "reply_to": payload["id"],
                    }
                ]
        return out + [{"type": "done", "in_reply_to": message["seq"]}]
