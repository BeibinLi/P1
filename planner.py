import re
from typing import (Any, Callable, Coroutine, Dict, List, Literal, Optional,
                    Tuple, Type, TypeVar, Union)

import autogen
from termcolor import colored


class P1Agent(autogen.AssistantAgent):
    def __init__(self, name, llm_config, max_traj_len=10, verbose=False):
        super().__init__(name=name, llm_config=llm_config)
        self.max_traj_len = max_traj_len
        self.verbose = verbose
        self.planner = autogen.AssistantAgent(name="planner", system_message=open("plan_sys_msg.md").read(), llm_config=llm_config)
        self.register_reply([autogen.Agent, None], P1Agent.generate_response)

    def generate_response(self, messages, sender, config=None):
        print("generate_response called from", sender)
        if sender == self:
            return False, ""  # Defer the LLM call to next reply functions.
        messages = self._oai_messages[sender] if messages is None else messages
        prompt = messages[-1]["content"]
        if prompt.strip() == "":  # Sanity check: if empty input. Stop.
            return True, "TERMINATE"
        traj = f"User Question: {prompt}\n\n--- Your Plan Trajectory ---\n\n"
        for i in range(self.max_traj_len):
            self.planner.clear_history()
            self.send(message=traj + f"\n\n------\nNow, plan step {i + 1}.\n", recipient=self.planner, request_reply=True, silent=True)
            _reply = self.planner.last_message()["content"]
            matched = re.findall("DECISION(\s*)*:(.+)", _reply, re.DOTALL)
            action = matched[-1][1].strip("* \n").rstrip("* \n") if matched else [line for line in _reply.split("\n") if line.strip()][-1]
            if self.verbose:
                print(colored(f">>> Step {i + 1}: {action}", "green"))
            if "TERMINATE" in action:
                break
            traj += f"--- Step {i + 1} ---\n{action}\n\n"
        traj += f"--- End of Your Plan Trajectory ---\nPlease answer the user's question: {prompt}"
        self.send(message=traj, recipient=self, request_reply=True, silent=True)
        return True, self._oai_messages[self][-1]


def p1_reply(question: str, config_list: list, verbose: bool = False) -> str:
    global total_cost
    o1_agent = P1Agent(name="o1_agent", llm_config={"config_list": config_list}, verbose=verbose)
    user_proxy = autogen.UserProxyAgent(name="user_proxy", human_input_mode="NEVER", code_execution_config={"use_docker": False}, max_consecutive_auto_reply=10)
    ans = user_proxy.initiate_chat(o1_agent, message=question, summary_method="reflection_with_llm")
    return ans.summary

