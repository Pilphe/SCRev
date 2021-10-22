import time
import json
import urllib
from mitmproxy import ctx
from mitmproxy.script import concurrent

class SCREV:
    def __init__(self):
        self.collection = []
        self.reset()

    def reset(self):
        self.collection.clear()
        self.collection_flow = None
        self.fetch_count = 0
        self.fetch_done = False

    @concurrent
    def request(self, flow):
        if hasattr(flow.request, "is_replay"):
            return

        if self.is_api_request(flow):
            if self.is_comments_request(flow):
                flow.kill()
                return
            elif self.is_likes_request(flow) or self.is_reposts_request(flow):
                if flow.request.query["offset"] == "0":
                    if self.fetch_count > 0:
                        self.reset()
                    flow.request.query["limit"] = "200"
                self.mark_request(flow)

    def response(self, flow):
        if not self.is_request_marked(flow):
            return

        '''
        if self.is_likes_request(flow) and flow.request.path_components[1] == "251087":
            with open("251087.json") as f:
                flow.response.text = json.dumps(json.load(f))
                return
        '''

        likes = json.loads(flow.response.text)
        self.update_collection(likes)

        if self.fetch_count == 0:
            self.collection_flow = flow
            self.pause_flow(self.collection_flow)
        self.fetch_count += 1
        print("Fetch {}".format(self.fetch_count))

        if likes["next_href"] is None:
            self.fetch_done = True
            self.collection["next_href"] = None
            '''
            if self.is_likes_request(self.collection_flow) and self.collection_flow.request.path_components[1] == "251087":
                with open("251087.json", "w") as f:
                    json.dump(self.collection, f)
                    self.collection_flow.kill()
            else:
            '''
            self.collection_flow.response.text = json.dumps(self.collection)
            self.resume_flow(self.collection_flow)
            self.reset()
        else:
            self.fetch_next_collection(flow, likes["next_href"])

    def mark_request(self, flow):
        flow.request.marked = True    

    def is_request_marked(self, flow):
        return hasattr(flow.request, "marked")

    def is_likes_request(self, flow):
        return ((len(flow.request.path_components) == 3) and (flow.request.path_components[2] == "likes"))

    def is_reposts_request(self, flow):
        return ((len(flow.request.path_components) == 4) and (flow.request.path_components[3] == "reposts"))
        
    def is_comments_request(self, flow):
        return ((len(flow.request.path_components) == 3) and (flow.request.path_components[2] == "comments"))

    def is_api_request(self, flow):
        return ((flow.request.host == "api-v2.soundcloud.com") and (flow.request.method == "GET"))

    def duplicate_flow(self, flow):
        dup = flow.copy()
        self.mark_request(dup)
        return dup

    def pause_flow(self, flow):
        flow.reply.take()

    def resume_flow(self, flow):
        #flow.reply.ack()
        flow.reply.commit()

    def update_collection(self, likes):
        likes["collection"].reverse()
        if not self.collection:
            self.collection = likes
        else:
            self.collection["collection"] = likes["collection"] + self.collection["collection"]

    def fetch_next_collection(self, flow, next):
        dup = self.duplicate_flow(flow)
        dup.request.query["offset"] = urllib.parse.parse_qs(urllib.parse.urlparse(next).query)["offset"][0]
        ctx.master.commands.call("replay.client", [dup])
    
addons = [
    SCREV()
]