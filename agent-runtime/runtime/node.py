#图节点，用于描述agent之间关系，每一个node就是一个agent
class Node:

    def __init__(self, name, agent):
        self.name = name
        self.agent = agent
        self.edges = []

    def connect(self, condition, next_node):
        self.edges.append((condition, next_node))