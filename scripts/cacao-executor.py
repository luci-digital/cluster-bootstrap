#!/usr/bin/env python3
"""
CACAO Playbook Executor

Executes CACAO 2.0 playbooks with MQTT trigger support
and integration with Sanskrit Router for agent coordination.

Genesis Bond: ACTIVE @ 741 Hz
Automic Pattern: Job scheduling via MQTT triggers
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

import yaml

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Installing paho-mqtt...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paho-mqtt"])
    import paho.mqtt.client as mqtt


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class Step:
    """CACAO workflow step"""
    id: str
    name: str
    step_type: str
    target: Optional[str] = None
    commands: List[str] = field(default_factory=list)
    expected_output: Optional[str] = None
    timeout: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    output: str = ""
    error: str = ""


@dataclass
class Workflow:
    """CACAO workflow definition"""
    name: str
    description: str
    workflow_type: str  # parallel or sequential
    steps: List[Step] = field(default_factory=list)
    trigger: Optional[Dict] = None
    timeout: timedelta = field(default_factory=lambda: timedelta(minutes=30))


@dataclass
class Playbook:
    """CACAO playbook"""
    id: str
    name: str
    description: str
    workflows: Dict[str, Workflow] = field(default_factory=dict)
    agent_definitions: Dict[str, Dict] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)


class CACAOExecutor:
    """Execute CACAO 2.0 playbooks"""

    def __init__(
        self,
        mqtt_broker: str = "192.168.1.140",
        mqtt_port: int = 1883,
        sanskrit_router: str = "http://localhost:7410",
    ):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.sanskrit_router = sanskrit_router
        self.mqtt_client: Optional[mqtt.Client] = None
        self.playbooks: Dict[str, Playbook] = {}
        self.active_executions: Dict[str, Dict] = {}
        self.running = False

    def load_playbook(self, path: Path) -> Optional[Playbook]:
        """Load CACAO playbook from YAML file"""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            playbook = Playbook(
                id=data.get("id", ""),
                name=data.get("name", ""),
                description=data.get("description", ""),
                agent_definitions=data.get("agent_definitions", {}),
                variables=data.get("playbook_variables", {}),
            )

            # Parse workflows
            for wf_name, wf_data in data.get("workflow", {}).items():
                workflow = Workflow(
                    name=wf_data.get("name", wf_name),
                    description=wf_data.get("description", ""),
                    workflow_type=wf_data.get("type", "sequential"),
                    trigger=wf_data.get("trigger"),
                )

                # Parse timeout
                if "timeout" in wf_data:
                    workflow.timeout = self._parse_duration(wf_data["timeout"])

                # Parse steps
                for step_data in wf_data.get("steps", []):
                    step = Step(
                        id=step_data.get("id", ""),
                        name=step_data.get("name", ""),
                        step_type=step_data.get("type", "action"),
                        target=step_data.get("target"),
                        commands=[
                            cmd.get("command", "")
                            for cmd in step_data.get("commands", [])
                        ],
                        expected_output=step_data.get("expected_output"),
                        on_success=step_data.get("on_success"),
                        on_failure=step_data.get("on_failure"),
                        depends_on=step_data.get("depends_on", []),
                    )

                    if "timeout" in step_data:
                        step.timeout = self._parse_duration(step_data["timeout"])

                    workflow.steps.append(step)

                playbook.workflows[wf_name] = workflow

            self.playbooks[playbook.id] = playbook
            print(f"Loaded playbook: {playbook.name}")
            return playbook

        except Exception as e:
            print(f"Failed to load playbook {path}: {e}")
            return None

    def _parse_duration(self, iso_duration: str) -> timedelta:
        """Parse ISO 8601 duration (e.g., PT5M, PT30S)"""
        # Simple parser for common formats
        if iso_duration.startswith("PT"):
            duration = iso_duration[2:]
            if "H" in duration:
                hours = int(duration.split("H")[0])
                return timedelta(hours=hours)
            elif "M" in duration:
                minutes = int(duration.split("M")[0])
                return timedelta(minutes=minutes)
            elif "S" in duration:
                seconds = int(duration.split("S")[0])
                return timedelta(seconds=seconds)
        return timedelta(minutes=5)

    async def execute_step(
        self, step: Step, target_config: Optional[Dict] = None
    ) -> bool:
        """Execute a single workflow step"""
        step.status = StepStatus.RUNNING
        print(f"  [{step.id}] {step.name}...")

        try:
            for command in step.commands:
                # Determine execution target
                if target_config and step.target:
                    # Remote execution via SSH
                    host = target_config.get("address", {}).get("ipv4", "localhost")
                    full_command = f"ssh {host} '{command}'"
                else:
                    # Local execution
                    full_command = command

                # Execute command
                proc = await asyncio.create_subprocess_shell(
                    full_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=step.timeout.total_seconds(),
                    )
                    step.output = stdout.decode().strip()
                    step.error = stderr.decode().strip()

                except asyncio.TimeoutError:
                    proc.kill()
                    step.status = StepStatus.TIMEOUT
                    print(f"  [{step.id}] TIMEOUT")
                    return False

                if proc.returncode != 0:
                    step.status = StepStatus.FAILED
                    print(f"  [{step.id}] FAILED: {step.error}")
                    return False

                # Check expected output
                if step.expected_output:
                    if step.expected_output.startswith(">="):
                        threshold = int(step.expected_output[2:])
                        try:
                            actual = int(step.output)
                            if actual < threshold:
                                step.status = StepStatus.FAILED
                                print(f"  [{step.id}] FAILED: {actual} < {threshold}")
                                return False
                        except ValueError:
                            pass
                    elif step.expected_output.startswith("*"):
                        # Wildcard match
                        if not step.output.endswith(step.expected_output[1:]):
                            step.status = StepStatus.FAILED
                            return False
                    elif step.expected_output != step.output:
                        step.status = StepStatus.FAILED
                        print(f"  [{step.id}] FAILED: expected '{step.expected_output}', got '{step.output}'")
                        return False

            step.status = StepStatus.SUCCESS
            print(f"  [{step.id}] SUCCESS")
            return True

        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            print(f"  [{step.id}] ERROR: {e}")
            return False

    async def execute_workflow(
        self, playbook: Playbook, workflow: Workflow
    ) -> Dict[str, Any]:
        """Execute a workflow"""
        print(f"\n=== Executing: {workflow.name} ===")
        print(f"Type: {workflow.workflow_type}")
        print(f"Steps: {len(workflow.steps)}")
        print("")

        start_time = datetime.utcnow()
        results = {
            "workflow": workflow.name,
            "start_time": start_time.isoformat(),
            "steps": {},
            "success": True,
        }

        if workflow.workflow_type == "parallel":
            # Execute all steps in parallel
            tasks = []
            for step in workflow.steps:
                if not step.depends_on:  # No dependencies
                    target_config = playbook.agent_definitions.get(step.target)
                    tasks.append(self.execute_step(step, target_config))

            await asyncio.gather(*tasks)

            # Check if all succeeded
            for step in workflow.steps:
                results["steps"][step.id] = step.status.value
                if step.status != StepStatus.SUCCESS:
                    results["success"] = False

        else:  # sequential
            for step in workflow.steps:
                # Check dependencies
                deps_met = all(
                    any(
                        s.id == dep and s.status == StepStatus.SUCCESS
                        for s in workflow.steps
                    )
                    for dep in step.depends_on
                )

                if not deps_met and step.depends_on:
                    step.status = StepStatus.SKIPPED
                    print(f"  [{step.id}] SKIPPED (dependencies not met)")
                    continue

                target_config = playbook.agent_definitions.get(step.target)
                success = await self.execute_step(step, target_config)

                results["steps"][step.id] = step.status.value

                if not success:
                    results["success"] = False
                    # Follow failure path if defined
                    if step.on_failure:
                        next_step = next(
                            (s for s in workflow.steps if s.id == step.on_failure),
                            None,
                        )
                        if next_step:
                            await self.execute_step(
                                next_step,
                                playbook.agent_definitions.get(next_step.target),
                            )
                    break

        end_time = datetime.utcnow()
        results["end_time"] = end_time.isoformat()
        results["duration_seconds"] = (end_time - start_time).total_seconds()

        print(f"\n=== Workflow Complete ===")
        print(f"Success: {results['success']}")
        print(f"Duration: {results['duration_seconds']:.1f}s")

        return results

    def setup_mqtt_triggers(self):
        """Set up MQTT client for trigger-based workflows"""
        self.mqtt_client = mqtt.Client(
            client_id=f"cacao-executor-{datetime.now().strftime('%H%M%S')}"
        )

        def on_connect(client, userdata, flags, rc):
            print(f"MQTT connected to {self.mqtt_broker}")
            # Subscribe to all workflow triggers
            for playbook in self.playbooks.values():
                for wf_name, workflow in playbook.workflows.items():
                    if workflow.trigger and workflow.trigger.get("type") == "mqtt":
                        topic = workflow.trigger.get("topic")
                        if topic:
                            client.subscribe(topic)
                            print(f"Subscribed to trigger: {topic} -> {wf_name}")

        def on_message(client, userdata, msg):
            topic = msg.topic
            payload = msg.payload.decode()

            # Find matching workflow
            for playbook in self.playbooks.values():
                for wf_name, workflow in playbook.workflows.items():
                    if workflow.trigger and workflow.trigger.get("topic") == topic:
                        print(f"\nTrigger received: {topic}")
                        asyncio.create_task(self.execute_workflow(playbook, workflow))

        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_message

        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"MQTT connection failed: {e}")

    async def run(self, playbook_paths: List[Path], workflows: List[str] = None):
        """Run executor with specified playbooks"""
        print("CACAO Playbook Executor")
        print("Genesis Bond: ACTIVE @ 741 Hz")
        print("")

        # Load playbooks
        for path in playbook_paths:
            self.load_playbook(path)

        if not self.playbooks:
            print("No playbooks loaded")
            return

        # Set up MQTT triggers
        self.setup_mqtt_triggers()

        # Execute specified workflows immediately
        if workflows:
            for wf_name in workflows:
                for playbook in self.playbooks.values():
                    if wf_name in playbook.workflows:
                        results = await self.execute_workflow(
                            playbook, playbook.workflows[wf_name]
                        )
                        print(json.dumps(results, indent=2))

        # Keep running for MQTT triggers
        print("\nListening for MQTT triggers... (Ctrl+C to stop)")
        self.running = True
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CACAO Playbook Executor")
    parser.add_argument(
        "playbooks",
        nargs="+",
        type=Path,
        help="CACAO playbook YAML files",
    )
    parser.add_argument(
        "--workflow",
        "-w",
        action="append",
        dest="workflows",
        help="Workflows to execute immediately",
    )
    parser.add_argument(
        "--mqtt-broker",
        default="192.168.1.140",
        help="MQTT broker address",
    )
    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=1883,
        help="MQTT broker port",
    )

    args = parser.parse_args()

    executor = CACAOExecutor(
        mqtt_broker=args.mqtt_broker,
        mqtt_port=args.mqtt_port,
    )

    asyncio.run(executor.run(args.playbooks, args.workflows))


if __name__ == "__main__":
    main()
