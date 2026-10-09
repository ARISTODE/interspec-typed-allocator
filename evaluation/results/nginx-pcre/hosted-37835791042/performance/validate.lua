threads = {}
function setup(thread) table.insert(threads, thread) end
function init(args) bad = 0; validated = 0 end
function response(status, headers, body)
  validated = validated + 1
  if status ~= 200 or body ~= "item:123:alpha" then bad = bad + 1 end
end
function done(summary, latency, requests)
  local failed = 0; local checked = 0
  for _, t in ipairs(threads) do
    failed = failed + t:get("bad"); checked = checked + t:get("validated")
  end
  io.write(string.format('INTERSPEC_WRK {"requests":%d,"duration_us":%d,"validated":%d,"bad":%d,"p50_us":%.3f,"p99_us":%.3f,"connect_errors":%d,"read_errors":%d,"write_errors":%d,"status_errors":%d,"timeouts":%d}\n',
    summary.requests, summary.duration, checked, failed, latency:percentile(50), latency:percentile(99),
    summary.errors.connect, summary.errors.read, summary.errors.write, summary.errors.status, summary.errors.timeout))
end
