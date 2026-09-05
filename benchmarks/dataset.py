from typing import List, Dict, Any

BENCHMARK_SUITE: List[Dict[str, Any]] = [
    {
        "id": "PY-01",
        "name": "Zero Division on Empty Input",
        "language": "python",
        "category": "logic_bug",
        "filename": "solution.py",
        "description": "Function crashes with ZeroDivisionError when called with an empty list.",
        "buggy_code": """def calculate_mean(numbers: list) -> float:
    total = sum(numbers)
    # Bug: Division by zero when numbers is empty
    return total / len(numbers)
""",
        "test_code": """from solution import calculate_mean

def test_regular_numbers():
    assert calculate_mean([10, 20, 30]) == 20.0

def test_single_number():
    assert calculate_mean([5]) == 5.0

def test_empty_list():
    assert calculate_mean([]) == 0.0
""",
        "ground_truth_fixed_code": """def calculate_mean(numbers: list) -> float:
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)
"""
    },
    {
        "id": "PY-02",
        "name": "Mutable Default Argument State Leak",
        "language": "python",
        "category": "state_leak",
        "filename": "solution.py",
        "description": "Default argument items=[] retains mutated state across separate function invocations.",
        "buggy_code": """def append_timestamp(event_name: str, events: list = []) -> list:
    # Bug: Mutable default argument retains state across calls
    events.append(event_name)
    return events
""",
        "test_code": """from solution import append_timestamp

def test_first_call():
    res1 = append_timestamp("login")
    assert res1 == ["login"]

def test_second_call_isolated():
    # Should not contain "login" from previous call
    res2 = append_timestamp("logout")
    assert res2 == ["logout"]
""",
        "ground_truth_fixed_code": """def append_timestamp(event_name: str, events: list = None) -> list:
    if events is None:
        events = []
    events.append(event_name)
    return events
"""
    },
    {
        "id": "PY-03",
        "name": "Off-by-One Loop Bounds IndexError",
        "language": "python",
        "category": "off_by_one",
        "filename": "solution.py",
        "description": "Loop iterates to len(items) + 1 resulting in an IndexError on the final iteration.",
        "buggy_code": """def compute_running_differences(values: list) -> list:
    if len(values) < 2:
        return []
    diffs = []
    # Bug: range(len(values)) causes values[i+1] to throw IndexError at last index
    for i in range(len(values)):
        diff = values[i + 1] - values[i]
        diffs.append(diff)
    return diffs
""",
        "test_code": """from solution import compute_running_differences

def test_simple_series():
    assert compute_running_differences([1, 4, 9, 16]) == [3, 5, 7]

def test_two_elements():
    assert compute_running_differences([10, 25]) == [15]

def test_single_element():
    assert compute_running_differences([42]) == []
""",
        "ground_truth_fixed_code": """def compute_running_differences(values: list) -> list:
    if len(values) < 2:
        return []
    diffs = []
    for i in range(len(values) - 1):
        diff = values[i + 1] - values[i]
        diffs.append(diff)
    return diffs
"""
    },
    {
        "id": "PY-04",
        "name": "Unclosed Resource and Missing Key Crash",
        "language": "python",
        "category": "resource_leak",
        "filename": "solution.py",
        "description": "Function accesses dictionary key directly without default and leaks open file handles.",
        "buggy_code": """def parse_user_config(config_dict: dict, key: str) -> str:
    # Bug: KeyError when key does not exist in config_dict
    val = config_dict[key]
    return val.strip().lower()
""",
        "test_code": """from solution import parse_user_config

def test_existing_key():
    assert parse_user_config({"theme": "  DARK "}, "theme") == "dark"

def test_missing_key():
    assert parse_user_config({}, "missing_key") == ""
""",
        "ground_truth_fixed_code": """def parse_user_config(config_dict: dict, key: str) -> str:
    val = config_dict.get(key, "")
    if not isinstance(val, str):
        return ""
    return val.strip().lower()
"""
    },
    {
        "id": "JS-01",
        "name": "JavaScript Array Bounds Off-by-One",
        "language": "javascript",
        "category": "off_by_one",
        "filename": "solution.js",
        "description": "Loop condition i <= arr.length accesses out-of-bounds element producing NaN.",
        "buggy_code": """function calculateSum(numbers) {
    let sum = 0;
    // Bug: i <= numbers.length causes numbers[numbers.length] to evaluate to undefined -> NaN
    for (let i = 0; i <= numbers.length; i++) {
        sum += numbers[i];
    }
    return sum;
}

module.exports = { calculateSum };
""",
        "test_code": """const test = require('node:test');
const assert = require('node:assert');
const { calculateSum } = require('./solution');

test('calculates correct array sum', () => {
    assert.strictEqual(calculateSum([1, 2, 3, 4]), 10);
});

test('handles empty array', () => {
    assert.strictEqual(calculateSum([]), 0);
});
""",
        "ground_truth_fixed_code": """function calculateSum(numbers) {
    let sum = 0;
    for (let i = 0; i < numbers.length; i++) {
        sum += numbers[i];
    }
    return sum;
}

module.exports = { calculateSum };
"""
    },
    {
        "id": "JS-02",
        "name": "Prototype Pollution in Object Merge",
        "language": "javascript",
        "category": "security_flaw",
        "filename": "solution.js",
        "description": "Recursive merge without checking dangerous __proto__ and constructor keys.",
        "buggy_code": """function safeMerge(target, source) {
    for (let key in source) {
        // Bug: Does not block __proto__ or constructor allowing Prototype Pollution
        if (typeof source[key] === 'object' && source[key] !== null) {
            if (!target[key]) target[key] = {};
            safeMerge(target[key], source[key]);
        } else {
            target[key] = source[key];
        }
    }
    return target;
}

module.exports = { safeMerge };
""",
        "test_code": """const test = require('node:test');
const assert = require('node:assert');
const { safeMerge } = require('./solution');

test('merges standard objects correctly', () => {
    const res = safeMerge({ a: 1 }, { b: 2 });
    assert.strictEqual(res.a, 1);
    assert.strictEqual(res.b, 2);
});

test('blocks prototype pollution payload', () => {
    const payload = JSON.parse('{"__proto__": {"polluted": "yes"}}');
    safeMerge({}, payload);
    assert.strictEqual(({}).polluted, undefined);
});
""",
        "ground_truth_fixed_code": """function safeMerge(target, source) {
    for (let key in source) {
        if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
            continue;
        }
        if (typeof source[key] === 'object' && source[key] !== null) {
            if (!target[key]) target[key] = {};
            safeMerge(target[key], source[key]);
        } else {
            target[key] = source[key];
        }
    }
    return target;
}

module.exports = { safeMerge };
"""
    },
    {
        "id": "JS-03",
        "name": "Unhandled Async Exception & Default Fallback",
        "language": "javascript",
        "category": "error_handling",
        "filename": "solution.js",
        "description": "Async parsing function throws unhandled exception on malformed JSON.",
        "buggy_code": """async function parsePayloadAsync(jsonString) {
    // Bug: Throws unhandled SyntaxError on invalid JSON instead of returning default fallback
    const parsed = JSON.parse(jsonString);
    return parsed.data;
}

module.exports = { parsePayloadAsync };
""",
        "test_code": """const test = require('node:test');
const assert = require('node:assert');
const { parsePayloadAsync } = require('./solution');

test('parses valid JSON string', async () => {
    const res = await parsePayloadAsync('{"data": "success"}');
    assert.strictEqual(res, 'success');
});

test('gracefully handles invalid JSON by returning null', async () => {
    const res = await parsePayloadAsync('{malformed: json');
    assert.strictEqual(res, null);
});
""",
        "ground_truth_fixed_code": """async function parsePayloadAsync(jsonString) {
    try {
        const parsed = JSON.parse(jsonString);
        return parsed && parsed.data !== undefined ? parsed.data : null;
    } catch (e) {
        return null;
    }
}

module.exports = { parsePayloadAsync };
"""
    },
    {
        "id": "JS-04",
        "name": "Event Listener Memory Leak Cleanup",
        "language": "javascript",
        "category": "concurrency_leak",
        "filename": "solution.js",
        "description": "Event subscriber class attaches listener but lacks unsubscribe method causing memory retention.",
        "buggy_code": """class EventWatcher {
    constructor(emitter) {
        this.emitter = emitter;
        this.count = 0;
        this.handler = () => { this.count++; };
        // Attaches listener
        this.emitter.on('event', this.handler);
    }

    // Bug: Missing dispose / cleanup method to remove listener
    getCount() {
        return this.count;
    }
}

module.exports = { EventWatcher };
""",
        "test_code": """const test = require('node:test');
const assert = require('node:assert');
const EventEmitter = require('events');
const { EventWatcher } = require('./solution');

test('tracks event count correctly', () => {
    const emitter = new EventEmitter();
    const watcher = new EventWatcher(emitter);
    emitter.emit('event');
    assert.strictEqual(watcher.getCount(), 1);
});

test('provides dispose method that removes listener', () => {
    const emitter = new EventEmitter();
    const watcher = new EventWatcher(emitter);
    assert.strictEqual(emitter.listenerCount('event'), 1);
    
    assert.strictEqual(typeof watcher.dispose, 'function');
    watcher.dispose();
    assert.strictEqual(emitter.listenerCount('event'), 0);
});
""",
        "ground_truth_fixed_code": """class EventWatcher {
    constructor(emitter) {
        this.emitter = emitter;
        this.count = 0;
        this.handler = () => { this.count++; };
        this.emitter.on('event', this.handler);
    }

    getCount() {
        return this.count;
    }

    dispose() {
        if (this.emitter && this.handler) {
            this.emitter.removeListener('event', this.handler);
        }
    }
}

module.exports = { EventWatcher };
"""
    }
]
