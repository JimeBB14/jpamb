#!/usr/bin/env python3
""" The extended interpreter for handling bytecode operations.
"""

from dataclasses import dataclass
from pathlib import Path
import sys
print(f"Arguments passed: {sys.argv}")

import logging
from typing import Literal, TypeAlias, Optional

l = logging
l.basicConfig(level=logging.DEBUG, format="%(message)s")

JvmType: TypeAlias = Literal["boolean"] | Literal["int"]

@dataclass(frozen=True)
class MethodId:
    class_name: str
    method_name: str
    params: list[JvmType]
    return_type: Optional[JvmType]

    @classmethod
    def parse(cls, name):
        import re

        TYPE_LOOKUP: dict[str, JvmType] = {
            "Z": "boolean",
            "I": "int",
        }

        RE = (
            r"(?P<class_name>.+)\.(?P<method_name>.*)\:\((?P<params>.*)\)(?P<return>.*)"
        )
        if not (i := re.match(RE, name)):
            l.error("invalid method name: %r", name)
            sys.exit(-1)

        return cls(
            class_name=i["class_name"],
            method_name=i["method_name"],
            params=[TYPE_LOOKUP[p] for p in i["params"]],
            return_type=None if i["return"] == "V" else TYPE_LOOKUP[i["return"]],
        )

    def classfile(self):
        return Path("decompiled", *self.class_name.split(".")).with_suffix(".json")

    def load(self):
        import json

        classfile = self.classfile()
        with open(classfile) as f:
            l.debug(f"Read decompiled classfile {classfile}")
            classfile = json.load(f)
        for m in classfile["methods"]:
            if (
                m["name"] == self.method_name
                and len(self.params) == len(m["params"])
                and all(
                    p == t["type"]["base"] for p, t in zip(self.params, m["params"])
                )
            ):
                return m
        else:
            print("Could not find method")
            sys.exit(-1)

    def create_interpreter(self, inputs):
        method = self.load()
        return ExtendedInterpreter(
            bytecode=method["code"]["bytecode"],
            locals=inputs,
            stack=[],
            pc=0,
        )


@dataclass
class ExtendedInterpreter:
    bytecode: list
    locals: list
    stack: list
    pc: int
    done: Optional[str] = None

    def interpret(self, limit=100):
        for i in range(limit):
            next_instruction = self.bytecode[self.pc]
            l.debug(f"STEP {i}:")
            l.debug(f"  PC: {self.pc} {next_instruction}")
            l.debug(f"  LOCALS: {self.locals}")
            l.debug(f"  STACK: {self.stack}")

            if fn := getattr(self, "step_" + next_instruction["opr"], None):
                fn(next_instruction)
            else:
                return f"can't handle {next_instruction['opr']!r}"

            if self.done:
                break
        else:
            self.done = "out of time"

        l.debug(f"DONE {self.done}")
        l.debug(f"  LOCALS: {self.locals}")
        l.debug(f"  STACK: {self.stack}")

        return self.done

    # Stack manipulation
    def step_push(self, bc):
        self.stack.insert(0, bc["value"]["value"])
        self.pc += 1

    def step_pop(self, bc):
        self.stack.pop(0)
        self.pc += 1

    def step_dup(self, bc):
        self.stack.insert(0, self.stack[0])
        self.pc += 1

    def step_swap(self, bc):
        self.stack[0], self.stack[1] = self.stack[1], self.stack[0]
        self.pc += 1

    def step_nop(self, bc):
        self.pc += 1

    # Arithmetic operations
    def step_add(self, bc):
        val1 = self.stack.pop(0)
        val2 = self.stack.pop(0)
        self.stack.insert(0, val1 + val2)
        self.pc += 1

    def step_subtract(self, bc):
        val1 = self.stack.pop(0)
        val2 = self.stack.pop(0)
        self.stack.insert(0, val2 - val1)  # Ensure correct operand order
        self.pc += 1

    def step_multiply(self, bc):
        val1 = self.stack.pop(0)
        val2 = self.stack.pop(0)
        self.stack.insert(0, val1 * val2)
        self.pc += 1

    def step_divide(self, bc):
        val1 = self.stack.pop(0)
        val2 = self.stack.pop(0)
        if val1 == 0:
            self.done = "divide by zero"
        else:
            self.stack.insert(0, val2 // val1)
        self.pc += 1

    # Comparison operations
    def step_if_icmpge(self, bc):
        val1 = self.stack.pop(0)
        val2 = self.stack.pop(0)
        if val2 >= val1:
            self.pc = bc["target"]
        else:
            self.pc += 1

    def step_if_icmpne(self, bc):
        val1 = self.stack.pop(0)
        val2 = self.stack.pop(0)
        if val1 != val2:
            self.pc = bc["target"]
        else:
            self.pc += 1

    # Load and store operations
    def step_load(self, bc):
        index = bc["index"]
        value = self.locals[index]
        self.stack.insert(0, value)
        self.pc += 1

    def step_store(self, bc):
        index = bc["index"]
        self.locals[index] = self.stack.pop(0)
        self.pc += 1

    # Return statement handling
    def step_return(self, bc):
        if bc["type"] is not None:
            self.stack.pop(0)
        self.done = "ok"

    def step_ireturn(self, bc):
        self.done = self.stack.pop(0)

if __name__ == "__main__":
    methodid = MethodId.parse(sys.argv[1])
    inputs = []
    result = sys.argv[2][1:-1]
    if result != "":
        for i in result.split(","):
            if i == "true" or i == "false":
                inputs.append(i == "true")
            else:
                inputs.append(int(i))
    print(methodid.create_interpreter(inputs).interpret())
