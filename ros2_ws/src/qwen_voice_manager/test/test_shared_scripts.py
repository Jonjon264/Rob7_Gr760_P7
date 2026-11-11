import json
from pathlib import Path

from ament_index_python.packages import get_package_share_directory

from qwen_voice_manager.node import load_project_module


def test_packaged_agent_reads_packaged_map_and_rules():
    script = load_project_module('qwen_agent')
    config = Path(get_package_share_directory('qwen_voice_manager')) / 'config'
    agent = script.QwenAgent()
    assert agent.map_file.resolve() == (config / 'map.json').resolve()
    assert agent.rules_file.resolve() == (config / 'rules.txt').resolve()
    map_data = json.loads(agent.map_file.read_text(encoding='utf-8-sig'))
    point = {key: map_data[0][key] for key in ('name', 'x', 'y')}
    expected = [{'action': 'reach', 'destination': point}]
    replies = iter(['{}', json.dumps(expected)])
    agent._complete = lambda messages: next(replies)
    try:
        assert agent.ask('go to production') == (expected, '')
        prompt = agent._system_prompt(map_data)
        assert '{map}' not in prompt and '{actions}' not in prompt
    finally:
        agent.client.close()
