"""Check selected critical runtime/identity/API receipts; this does not run inference or handle secrets."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'evidence-2026-11-12'

def receipt(name):
    return json.loads((EVIDENCE / name).read_text())

def require(condition, message):
    if not condition:
        raise AssertionError(message)

manifest = json.loads((ROOT / 'comparison-grades.json').read_text())
paseo = receipt('paseo-delegation-result.json')
require(paseo['passed'] and paseo['parent_create_tool_calls'] == 1, 'Paseo actual child creation missing')
require(paseo['child']['ParentAgentId'] == paseo['parent']['Id'], 'Paseo child lineage mismatch')
require(paseo['parent_read_child_activity'] and paseo['parent_received_finish_notification'], 'Paseo result collection missing')
require(paseo['child_independent_assistant_marker_lines'] > 0, 'Paseo independent child output missing')
h3 = receipt('paseo-h3-followup.json')['checks']
require(all(h3[k] is True for k in ['login','interactive','configured_user_shell_matches_profile','backward_word_edit','forward_word_edit']), 'Paseo configured shell/input proof failed')
require(h3['private_declarations_detected'] == h3['private_declarations_defined'] > 0, 'Paseo startup declaration check failed')
paseo_primary = receipt('paseo-primary-receipts.json')
require(paseo_primary['anthropic_identity']['subscriptionType']=='enterprise' and paseo_primary['openai_identity']['plan_type']=='ent26', 'Paseo Enterprise classification missing')
require(paseo_primary['openai_plan_primary_mapping']['short_excerpt']=='Support the ent26 enterprise plan', 'Primary ent26 mapping missing')
require(all(paseo_primary['existing_accounts_requests'][provider]['assistant_marker_lines_observed']>0 for provider in ['claude','codex']), 'Paseo separate Enterprise responses missing')
primary = paseo_primary['openrouter_authenticated_request']
require(primary['request_exit'] == primary['timeline_exit'] == 0 and primary['separate_assistant_response'] == 'PASEO_OPENROUTER_OK', 'Paseo authenticated gateway response missing')
consent = receipt('paseo-config-consent-result.json')
require(consent['all_monitored_configs_unchanged'] and consent['all_monitored_skills_unchanged'], 'Paseo clean startup comparison failed')

sheprd = receipt('sheprd-validation-startup-guards.json')
require(sheprd['core'] == 'hc 0.1.18', 'Sheprd tested core version differs from declared setup')
require(sheprd['result'] == 'pass' and all(sheprd['guard_checks'].values()), 'Sheprd startup guards failed')
require(len(sheprd['new_terminal_addresses_after_action']) == 1, 'Sheprd new-terminal ownership missing')
require(not set(sheprd['new_terminal_addresses_after_action']) & set(sheprd['terminal_addresses_before_action']), 'Sheprd terminal was not new')
require(all(sheprd['startup_trace'].values()) and sheprd['external_files_unchanged'], 'Sheprd startup/config evidence failed')
chat = receipt('sheprd-validation-final.json')
require(chat['native_chat_attached_and_shown'] and chat['native_chat_expected_reply_observed'], 'Sheprd native assistant receipt missing')
require(chat['delegation_child_get_exit'] == 0 and chat['delegation_child_record']['exit_code'] == 0, 'Sheprd child completion missing')
require(chat['delegation_lineage_matches_native_parent'] and chat['delegation_child_output_observed'], 'Sheprd child/result lineage missing')
require(chat['owned_profile_removed'] and chat['owned_core_stop_exit'] == chat['owned_app_exit'] == 0, 'Sheprd cleanup incomplete')

sheprd_identity=receipt('sheprd-enterprise-primary.json')['records']
require(len(sheprd_identity)==2 and all(r['passed'] and r['assistant_response_matches'] and r['exit_code']==0 and r['enterprise_identity_qualified'] for r in sheprd_identity), 'Sheprd actual Enterprise receipts missing')
agentastic_identity=receipt('agentastic-enterprise-primary.json')
require(agentastic_identity['claude']['enterprise_subscription_observed'] and agentastic_identity['codex']['plan_type']=='ent26', 'Agentastic Enterprise identity evidence missing')
require(all(agentastic_identity[p]['assistant_role_verified'] and agentastic_identity[p]['assistant_response']=='AGENTASTIC_OK' for p in ['claude','codex']), 'Agentastic native Enterprise responses missing')

keys = receipt('agentastic-validation-input.json')
require(keys['control_output_observed'] and keys['edited_output_observed'] and keys['unmodified_edit_output_absent'], 'Agentastic discriminating input test failed')
wiring = receipt('agentastic-startup-wiring.json')
require(wiring['actual_shell_matches_configured'] and all(wiring['actual_shell_boolean_receipts'].values()), 'Agentastic executable/startup evidence failed')
require(all(v['byte_identical'] for v in wiring['actual_generated_shims'].values()), 'Agentastic actual loader differs from inspected source')
provenance = receipt('agentastic-validation-provenance.json')
require(provenance['frontmost_check']['observed_pid'] == provenance['frontmost_check']['exact_target_pid'], 'Agentastic foreground target was not verified')
for capture in provenance['screenshots']:
    require(hashlib.sha256((EVIDENCE / capture['retained_crop']).read_bytes()).hexdigest() == capture['retained_crop_sha256'], 'Agentastic capture digest mismatch')
cleanup = receipt('agentastic-validation-cleanup.json')
require(not cleanup['agentastic_processes_remaining'] and not cleanup['known_new_paths_remaining'], 'Agentastic cleanup incomplete')
require(all(receipt('agentastic-delegation-primary.json')['checks'].values()), 'Agentastic primary delegation receipt missing')

pending = manifest['runtime_validation']['authenticated_api_pending']
for app in pending:
    require(manifest['apps'][app]['grades']['entry_keys']['grade'] == 'partial', f'{app}: wiring cannot stand in for authenticated inference')
    require(manifest['apps'][app]['status'] == 'unqualified', f'{app}: incomplete API inference cannot be a full pass')
print('PASS: actual runtime/primary receipts, lineage, startup, input, capture hashes and cleanup')
if pending:
    print('INCOMPLETE: authenticated API-key assistant replies need a valid disposable key for ' + ', '.join(pending))
    sys.exit(2)
for app in ['Sheprd','Agentastic']:
    refs=manifest['runtime_validation']['authenticated_api_receipts'][app]
    result=json.loads((ROOT / refs['response']).read_text())
    launch=json.loads((ROOT / refs['terminal_launch']).read_text())
    require(result['passed'] and result['executed'] and result['assistant_response_matches'] and result['exit_code']==0, f'{app}: authenticated response missing')
    require(result['actual_assistant_response']==result['marker']==launch['expected_marker'] and result['completed_assistant_text_parts']>0 and result['event_counts'].get('step_start',0)>0, f'{app}: independent typed assistant/marker evidence missing')
    require(result['key_present'] and not result['key_in_captured_output'], f'{app}: credential/result guard failed')
    require(result['tool_events']==result['error_events']==0 and result['temporary_profile_removed'], f'{app}: probe/cleanup failed')
    require(launch['app']==app and launch['owned_terminal_verified'] and launch['probe_started_in_app_terminal'] and launch['terminal_id'], f'{app}: host-app route missing')
    require(result['claimed_app_route']==launch['probe_route_label'] and (ROOT / launch['result_path']).resolve()==(ROOT / refs['response']).resolve(), f'{app}: probe result is not bound to the app launch')
print('COMPLETE: selected critical receipts and authenticated gateway/app routes verified; per-gate manual primary review remains separately documented')
