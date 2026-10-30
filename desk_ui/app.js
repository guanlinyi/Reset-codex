(() => {
'use strict';
const $=id=>document.getElementById(id), token=document.querySelector('meta[name="reset-token"]').content;
const strings={
  "zh": {
    "refresh": "刷新额度",
    "quota": "可用额度",
    "five": "5 小时限额",
    "week": "每周限额",
    "continuous": "持续推进",
    "target": "当前聊天",
    "recoveries": "等待 5 小时额度恢复次数",
    "start": "启动持续推进",
    "cancel": "取消持续推进",
    "chatHeading": "选择聊天窗口",
    "defaultChat": "默认选择最近可用聊天",
    "more": "加载更多聊天",
    "settings": "网络设置",
    "settingsHelp": "代理留空时跟随本机网络设置。",
    "model": "修改模型（可选）",
    "effort": "推理强度",
    "proxyHost": "代理地址",
    "proxyPort": "代理端口",
    "defaults": "恢复默认",
    "save": "保存设置",
    "source": "数据来源：Codex 官方账号接口",
    "connected": "官方数据已连接",
    "connecting": "等待官方数据",
    "updated": "更新于 ",
    "unread": "暂不可读",
    "remaining": "剩余",
    "noReset": "官方暂未提供恢复时间",
    "resetReached": "已到重置时间，等待官方确认",
    "resetSuffix": "后重置",
    "days": "天",
    "hours": "小时",
    "minutes": "分钟",
    "selecting": "正在选择默认聊天…",
    "search": "搜索聊天标题",
    "noChats": "暂无可用聊天，请稍后刷新。",
    "noMatch": "没有匹配的聊天，可加载更多。",
    "choose": "等待聊天列表",
    "view": "打开聊天终端 ↗",
    "viewExisting": "查看原终端 ↗",
    "opening": "正在打开…",
    "defaultModel": "不修改模型",
    "defaultEffort": "不修改推理强度",
    "defaultShort": "默认模型",
    "catalogMissing": "暂未取得列表",
    "defaultHost": "留空跟随系统",
    "defaultPort": "留空不设置代理",
    "blankHelp": "留空即使用默认设置。",
    "modelsHelp": "",
    "modelsUnavailable": "模型列表暂不可读，可保持默认或稍后刷新。",
    "unsaved": "修改尚未保存。",
    "saving": "正在保存…",
    "saved": "代理设置已保存。",
    "saveNotice": "代理设置已保存。模型只通过上方选择临时修改。",
    "loadFailed": "暂时连不上本机服务，请重新打开软件。",
    "dataFailed": "官方数据暂不可读，请检查 Codex 登录和本机代理。",
    "genericError": "操作尚未完成，请检查终端或稍后刷新。",
    "refreshDone": "额度与聊天标题已刷新。",
    "openDone": "已在 Windows Terminal 中打开聊天。",
    "reuseDone": "已接回同一个终端。",
    "viewerWait": "终端尚未确认接入，请检查终端窗口或权限提示。",
    "openUnknown": "打开结果尚未确认，请查看 Windows Terminal 后刷新。",
    "recoveryHelp": "每次恢复后自动再次发送推进指令。",
    "zeroRecoveries": "0 次 · 当前额度用完即停",
    "times": "次",
    "ready": "准备就绪",
    "modeStarted": "已启用，将向当前会话发送推进命令。",
    "modeCancelled": "已取消后续自动接续及关机；已发送的任务仍在终端执行。",
    "progress": "已恢复 {done} / {limit} 次",
    "waitingFor": "下次检查恢复时间：",
    "keepAwake": "电脑保持唤醒",
    "workingDir": "工作目录",
    "proxy": "代理",
    "modelInvalid": "请选择列表中的模型，或恢复默认。",
    "portInvalid": "端口需为 1–65535，或留空使用默认。",
    "hostInvalid": "请填写 IP 或主机名，例如 127.0.0.1。",
    "waitSettings": "正在读取设置，请稍候。",
    "activeOther": "当前任务保持在原聊天中运行。",
    "terminalHeading": "正在运行的聊天",
    "terminalCheck": "检查终端",
    "terminalChecking": "正在检查…",
    "terminalNotChecked": "点击检查，查看后台会话和已连接的终端。",
    "terminalNone": "没有发现正在运行的聊天或保留的终端。",
    "terminalCount": "发现 {n} 个终端 · 检查于 ",
    "terminalHelp": "这里只显示 Reset 管理的 Psmux 终端。“查看”接回原终端；批量结束只处理确认没有前端连接的后台会话。",
    "terminalBackground": "后台会话 · 未连接终端",
    "terminalAttached": "终端已连接",
    "terminalUnknown": "连接情况未确认",
    "terminalOpen": "查看",
    "terminalClose": "结束",
    "terminalReadOnly": "其他或身份未确认的终端 · 仅查看",
    "terminalConfirm": "结束“{title}”的终端？\n\n当前任务和未提交的输入会中断，聊天记录会保留。该聊天的持续推进也会停止。",
    "terminalClosed": "已结束所选聊天的运行，已保存的聊天记录保留。",
    "bulkEnd": "结束后台聊天",
    "bulkNone": "没有确认处于后台、可以结束的聊天。",
    "bulkConfirm": "将结束以下没有前端连接的聊天：\n{list}\n\n当前任务会中断，已保存的聊天记录保留。已经接回前端或身份发生变化的终端会跳过。",
    "bulkDone": "已结束 {closed} 个后台聊天，跳过 {skipped} 个已变化的终端。",
    "notOpen": "未在运行，无需结束。",
    "targetUnknown": "暂未确认目标进程，请重新检查终端。",
    "externalConfirm": "结束“{title}”（PID {pid}）中的 Codex 进程？\n\n当前聊天执行会停止，已保存的聊天记录保留。原 Windows Terminal 或终端窗口会保留。",
    "focused": "已切回这段聊天原来的终端窗口。",
    "hostManaged": "Reset 托管",
    "hostPsmux": "其他 Psmux 终端",
    "hostVscode": "Windows Terminal 终端",
    "hostConsole": "普通终端",
    "hostUnknown": "来源待确认",
    "unknownChat": "尚未关联聊天标题",
    "confirmUnknown": "现有 Codex（PID {pids}）尚未关联聊天标题，无法确定是否就是这段聊天。是否仍然新建终端恢复？如需避免重复，请先自行检查原终端。",
    "externalModeHelp": "此聊天在 Reset 以外的终端运行。请在合适的时候自行关闭原 Codex，再由 Reset 打开。",
    "sessionId": "会话 ID",
    "alreadyAttached": "这段会话已连接原来的 Windows Terminal 终端，请切回原窗口查看；未新开窗口。",
    "focusedExisting": "已切回原来的会话窗口，未新开窗口。",
    "revealedExisting": "已在原窗口显示对应的 Codex 终端。",
    "modelChangeHelp": "不选择则沿用该聊天原来的模型；选择后在打开或推进时切换。",
    "shutdownOption": "最后一轮额度耗尽后自动关机",
    "commandHelp": "启动后发送：持续推进至额度耗尽，确认独立任务结束后保存交接。取消只停止后续自动接续及关机。",
    "commandLabel": "推进指令",
    "commandText": "持续推进至额度耗尽，确认独立任务结束后保存交接",
    "cancelHelp": "取消会停止后续接续和自动关机，已发送的任务继续执行。",
    "autoGoal": "如果遇到目标恢复的弹窗自动取消",
    "autoUpdate": "如果遇到 Codex 更新自动更新",
    "handlingStart": "正在处理终端并发送推进指令…"
  },
  "en": {
    "refresh": "Refresh quota",
    "quota": "Available quota",
    "five": "5-hour limit",
    "week": "Weekly limit",
    "continuous": "Continuous work",
    "target": "Conversation",
    "recoveries": "5-hour quota recoveries to wait for",
    "start": "Start continuous work",
    "cancel": "Cancel continuous work",
    "chatHeading": "Select conversation",
    "defaultChat": "Latest available conversation selected",
    "more": "Load more conversations",
    "settings": "Network settings",
    "settingsHelp": "Blank proxy fields follow this computer’s network settings.",
    "model": "Change model (optional)",
    "effort": "Reasoning effort",
    "proxyHost": "Proxy host",
    "proxyPort": "Proxy port",
    "defaults": "Restore defaults",
    "save": "Save settings",
    "source": "Source: official Codex account API",
    "connected": "Official data connected",
    "connecting": "Waiting for official data",
    "updated": "Updated ",
    "unread": "Unavailable",
    "remaining": "left",
    "noReset": "Reset time is unavailable",
    "resetReached": "Reset time reached; awaiting official confirmation",
    "resetSuffix": "until reset",
    "days": "d",
    "hours": "h",
    "minutes": "min",
    "selecting": "Selecting a default conversation…",
    "search": "Search conversation titles",
    "noChats": "No conversations available. Refresh shortly.",
    "noMatch": "No matching titles. Try loading more.",
    "choose": "Waiting for conversations",
    "view": "Open chat terminal ↗",
    "viewExisting": "View existing terminal ↗",
    "opening": "Opening…",
    "defaultModel": "Do not change model",
    "defaultEffort": "Do not change effort",
    "defaultShort": "Default model",
    "catalogMissing": "catalog unavailable",
    "defaultHost": "Blank: system settings",
    "defaultPort": "Blank: no proxy override",
    "blankHelp": "Blank fields use defaults.",
    "modelsHelp": "",
    "modelsUnavailable": "Model list unavailable. Keep defaults or refresh later.",
    "unsaved": "Unsaved changes.",
    "saving": "Saving…",
    "saved": "Proxy settings saved.",
    "saveNotice": "Proxy settings saved. Model changes use the optional selector above.",
    "loadFailed": "Local service is unavailable. Reopen Reset.",
    "dataFailed": "Official data is unavailable. Check Codex login and your proxy.",
    "genericError": "Could not confirm the operation. Check the terminal or refresh.",
    "refreshDone": "Quota and conversation titles refreshed.",
    "openDone": "Conversation opened in Windows Terminal.",
    "reuseDone": "Reconnected to the same terminal.",
    "viewerWait": "The terminal is not yet connected. Check the terminal window and permission prompts.",
    "openUnknown": "Launch is not yet confirmed. Check Windows Terminal and refresh.",
    "recoveryHelp": "Each recovery automatically sends the continuation message again.",
    "zeroRecoveries": "0 · stop when current quota runs out",
    "times": "",
    "ready": "Ready",
    "modeStarted": "Enabled; sending a continuation message.",
    "modeCancelled": "Future continuation and shutdown cancelled. Submitted work remains in the terminal.",
    "progress": "Recoveries: {done} / {limit}",
    "waitingFor": "Next reset check: ",
    "keepAwake": "Computer stays awake",
    "workingDir": "Workspace",
    "proxy": "Proxy",
    "modelInvalid": "Choose a model from the list or restore defaults.",
    "portInvalid": "Use a port from 1 to 65535, or leave blank.",
    "hostInvalid": "Enter an IP address or hostname, such as 127.0.0.1.",
    "waitSettings": "Loading settings. Please wait.",
    "activeOther": "Work stays in the original conversation.",
    "terminalHeading": "Running conversations",
    "terminalCheck": "Check terminals",
    "terminalChecking": "Checking…",
    "terminalNotChecked": "Check for background sessions and connected terminals.",
    "terminalNone": "No running conversations or retained terminals found.",
    "terminalCount": "Found {n} terminals · Checked at ",
    "terminalHelp": "Only Psmux terminals managed by Reset are listed. View reconnects the original terminal; batch end affects only confirmed detached sessions.",
    "terminalBackground": "Background session · no client",
    "terminalAttached": "Terminal connected",
    "terminalUnknown": "Connection unconfirmed",
    "terminalOpen": "View",
    "terminalClose": "End",
    "terminalReadOnly": "External or unverified terminal · read only",
    "terminalConfirm": "End the terminal for “{title}”?\n\nRunning work and unsent input will be interrupted. Saved conversation history remains. Continuous work for this conversation will also stop.",
    "terminalClosed": "Selected conversation stopped. Saved history remains.",
    "bulkEnd": "End background chats",
    "bulkNone": "No confirmed background conversations are eligible to end.",
    "bulkConfirm": "End these conversations with no frontend connection:\n{list}\n\nRunning work will stop. Saved history remains. Reconnected or changed terminals will be skipped.",
    "bulkDone": "Ended {closed} background chats; skipped {skipped} changed terminals.",
    "notOpen": "Not running; nothing to end.",
    "targetUnknown": "Target identity is unavailable. Check terminals again.",
    "externalConfirm": "End Codex for “{title}” (PID {pid})?\n\nConversation execution will stop. Saved history remains. Its Windows Terminal or terminal window stays open.",
    "focused": "Returned to the conversation’s existing terminal window.",
    "hostManaged": "Managed by Reset",
    "hostPsmux": "External Psmux terminal",
    "hostVscode": "Windows Terminal terminal",
    "hostConsole": "Console terminal",
    "hostUnknown": "Host unconfirmed",
    "unknownChat": "Conversation title not yet associated",
    "confirmUnknown": "Existing Codex processes (PID {pids}) have no confirmed conversation identity. Open another terminal anyway? Check the original terminals first to avoid a duplicate.",
    "externalModeHelp": "This conversation is running outside Reset. When appropriate, close the original Codex yourself, then open it through Reset.",
    "sessionId": "Session ID",
    "alreadyAttached": "This session is already attached. Switch to its existing Windows Terminal terminal; no new window was opened.",
    "focusedExisting": "Returned to the existing session window; no new window was opened.",
    "revealedExisting": "The matching Codex terminal is visible in its existing window.",
    "modelChangeHelp": "Leave unchanged to keep this conversation’s model. A selection applies when opening or starting work.",
    "shutdownOption": "Shut down after the final quota round",
    "commandHelp": "Sends a continuation message. Cancel stops future continuation and shutdown; already submitted work remains in the terminal.",
    "commandLabel": "Continuation message",
    "commandText": "持续推进至额度耗尽，确认独立任务结束后保存交接",
    "cancelHelp": "Cancel stops future continuation and shutdown. Work already submitted keeps running.",
    "autoGoal": "Automatically dismiss the goal-resume prompt",
    "autoUpdate": "Automatically update Codex when prompted",
    "handlingStart": "Preparing the terminal and submitting your message…"
  }
};
const phases={
  "zh": {
    "idle": "未启动",
    "starting": "正在启动",
    "resuming": "正在接续",
    "running": "命令已发送 · 监测额度",
    "waiting_quota": "等待额度恢复",
    "cancelling": "正在取消",
    "cancelled": "已取消",
    "stopped": "已停止",
    "complete": "任务完成",
    "needs_attention": "需要处理",
    "awaiting_idle": "等待终端空闲",
    "shutdown_pending": "准备自动关机"
  },
  "en": {
    "idle": "Not started",
    "starting": "Starting",
    "resuming": "Resuming",
    "running": "Message sent · monitoring quota",
    "waiting_quota": "Waiting for quota",
    "cancelling": "Cancelling",
    "cancelled": "Cancelled",
    "stopped": "Stopped",
    "complete": "Task complete",
    "needs_attention": "Needs attention",
    "awaiting_idle": "Waiting for terminal to become idle",
    "shutdown_pending": "Shutdown countdown"
  }
};
const reasons={
  "zh": {
    "quota_exhausted": "额度已耗尽，等待官方确认恢复。",
    "recovery_limit": "已达到所选恢复次数，持续模式结束。",
    "task_complete": "任务已完成，持续模式结束。",
    "user_cancelled": "正在暂停目标并取消后续接续。",
    "service_restarted": "软件曾重新启动，请重新按启动按钮确认。",
    "terminal_not_ready": "无法确认空白输入或模型切换，已停止；请查看终端。",
    "resume_not_confirmed": "接续结果尚未确认，已停止自动重试。",
    "goal_paused": "目标已被暂停，自动接续已停止。",
    "goal_blocked": "任务需要补充信息，自动接续已停止。",
    "goal_budgetLimited": "目标预算已用完，请在 Codex 中处理。",
    "goal_cleared": "目标已清除，持续模式结束。",
    "pause_not_confirmed": "自动接续已取消；暂停结果待确认，请查看终端。",
    "keep_awake_failed": "无法确认电脑保持唤醒，模式未继续。",
    "terminal_closed": "聊天终端已结束，自动推进停止。",
    "terminal_close_unconfirmed": "已停止自动接续，请重新检查终端是否结束。",
    "shutdown_quota_changed": "额度状态已变化，自动关机已取消。",
    "shutdown_quota_unconfirmed": "无法重新确认额度耗尽，自动关机已取消。",
    "shutdown_failed": "Windows 未完成关机请求。",
    "shutdown_requested": "已向 Windows 请求关机。"
  },
  "en": {
    "quota_exhausted": "Quota exhausted. Waiting for official recovery confirmation.",
    "recovery_limit": "Selected recovery count reached. Continuous mode ended.",
    "task_complete": "Task complete. Continuous mode ended.",
    "user_cancelled": "Pausing the goal and cancelling future continuation.",
    "service_restarted": "Reset restarted. Press Start again to confirm.",
    "terminal_not_ready": "Could not confirm the input or model change. Check the terminal.",
    "resume_not_confirmed": "Resume was not confirmed. Automatic retries stopped.",
    "goal_paused": "Goal paused. Automatic continuation stopped.",
    "goal_blocked": "More information is needed. Automatic continuation stopped.",
    "goal_budgetLimited": "Goal budget exhausted. Review it in Codex.",
    "goal_cleared": "Goal cleared. Continuous mode ended.",
    "pause_not_confirmed": "Automatic continuation cancelled; check the terminal to confirm the goal paused.",
    "keep_awake_failed": "Could not keep the computer awake. Mode stopped.",
    "terminal_closed": "Terminal ended; automation stopped.",
    "terminal_close_unconfirmed": "Automatic continuation stopped. Check the terminal again.",
    "shutdown_quota_changed": "Quota changed; shutdown cancelled.",
    "shutdown_quota_unconfirmed": "Exhaustion could not be reconfirmed; shutdown cancelled.",
    "shutdown_failed": "Windows did not complete the shutdown request.",
    "shutdown_requested": "Shutdown requested."
  }
};
const terminalLabels={
  "zh": {
    "running": "Codex 运行中",
    "shell": "终端保留",
    "closed": "可新建终端",
    "external": "已在其他终端打开",
    "uncertain": "终端身份需核实",
    "conflict": "同一会话有其他终端"
  },
  "en": {
    "running": "Codex running",
    "shell": "Shell available",
    "closed": "Ready to open",
    "external": "Open in another terminal",
    "uncertain": "Verify terminal ownership",
    "conflict": "Other terminal holds this session"
  }
};
let terminalChecking=false;
let lang='zh',selected='',state=null,busy=false,pendingLoad=null,settingsDirty=false,settingsSaving=false,settingsSignature='',listSignature='',modeBusy=false,cancelRequested=false,manualSelection=false;
try{lang=localStorage.getItem('reset-language')==='en'?'en':'zh';selected=localStorage.getItem('reset-selected-thread')||sessionStorage.getItem('reset-selected-thread')||'';}catch{}
const t=key=>strings[lang][key]||key,locale=()=>lang==='zh'?'zh-CN':'en-US';
let actionNoticeUntil=0;
function notice(text,error=false){$('notice').textContent=text;$('notice').classList.toggle('notice-error',error);$('notice').setAttribute('role',error?'alert':'status');}
function actionNotice(text,error=false){actionNoticeUntil=Date.now()+30000;notice(text,error);}
function errorText(e){if(lang==='zh')return e.message||t('genericError');const s=e.message||'';return /Reset 以外/.test(s)?t('externalModeHelp'):/端口/.test(s)?t('portInvalid'):/地址/.test(s)?t('hostInvalid'):/模型|强度/.test(s)?t('modelInvalid'):t('genericError');}
async function api(path,data){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),(path.includes('/open')||path==='/api/continuous/start')?240000:65000);try{const options={headers:{'X-Reset-Desk':token},signal:controller.signal,cache:'no-store'};if(data!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(data);}const r=await fetch(path,options),body=await r.json();if(!r.ok||body.ok===false)throw Error(body.error||t('genericError'));return body;}finally{clearTimeout(timer);}}
function countdown(seconds){if(seconds<=0)return t('resetReached');const mins=Math.ceil(seconds/60),days=Math.floor(mins/1440),hours=Math.floor(mins%1440/60),rest=mins%60;return (days?days+' '+t('days')+' ':'')+(hours?hours+' '+t('hours')+' ':'')+(!days&&rest?rest+' '+t('minutes')+' ':'')+t('resetSuffix');}
function paintQuota(q){for(const [key,mins]of [['five',300],['week',10080]]){const w=(q.windows||[]).find(x=>x.windowDurationMins===mins),ok=q.available&&w&&Number.isFinite(w.usedPercent),remaining=ok?Math.max(0,Math.min(100,100-w.usedPercent)):null;$(key+'val').replaceChildren(document.createTextNode(remaining===null?'—':remaining+'%'));const small=document.createElement('small');small.textContent=t(remaining===null?'unread':'remaining');$(key+'val').append(small);$(key+'fill').style.width=(remaining||0)+'%';$(key+'fill').style.background=remaining===0?'#9b7b40':'#292e29';$(key+'bar').setAttribute('aria-label',t(key==='five'?'five':'week'));if(remaining===null)$(key+'bar').removeAttribute('aria-valuenow');else $(key+'bar').setAttribute('aria-valuenow',remaining);const reset=ok&&Number.isFinite(w.resetsAt);$(key+'reset').textContent=reset?countdown(w.resetsAt-Date.now()/1000):t('noReset');$(key+'date').textContent=reset?new Date(w.resetsAt*1000).toLocaleString(locale(),{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}):'';}$('connection').textContent=t(q.available?'connected':'connecting');$('freshness').textContent=state.checked_at?t('updated')+new Date(state.checked_at*1000).toLocaleTimeString(locale(),{hour12:false}):t('unread');}
function currentThread(){return (state?.threads||[]).find(x=>x.id===selected);}
function chooseDefault(){if(state?.continuous?.enabled){selected=state.continuous.thread_id;return;}const rows=state?.threads||[];if(!rows.length)return;const present=rows.find(x=>x.id===selected);if(!present||(!manualSelection&&!['running','shell','closed'].includes(present.terminal?.state))){const next=rows.find(x=>['running','shell','closed'].includes(x.terminal?.state))||rows[0];selected=next.id;try{localStorage.setItem('reset-selected-thread',selected);}catch{}}}
function paintSelection(){const row=currentThread(),terminal=row?.terminal?.state;$('selectedname').textContent=row?.name||t('selecting');if($('selected-id'))$('selected-id').textContent=row?t('sessionId')+' '+row.id:'';$('view').textContent=busy?t('opening'):t(terminal==='running'?'viewExisting':'view');$('view').disabled=busy||!row;$('actionhint').textContent=row?(terminalLabels[lang][terminal]||t('choose')):t('choose');paintMode();}
function terminalItem(row){return {...(row.terminal||{}),thread_id:row.id,name:row.name,can_open:true};}
function actionButtons(item){
 const buttons=document.createElement('div');buttons.className='terminal-buttons chat-actions';
 const view=document.createElement('button');view.type='button';view.className='secondary';view.textContent=t('terminalOpen');view.disabled=busy||item.can_open===false;
 view.title=view.disabled?t('targetUnknown'):t('terminalOpen');view.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();reconnectTerminal(item);});
 const end=document.createElement('button');end.type='button';end.className='terminal-end';end.textContent=t('terminalClose');end.disabled=busy||modeBusy||!item.can_close;
 end.title=end.disabled?t(item.state==='closed'?'notOpen':'targetUnknown'):t('terminalClose');end.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();endTerminal(item);});
 buttons.append(view,end);return buttons;
}
function paintList(){
 const query=$('search').value.trim().toLowerCase(),rows=(state.threads||[]).filter(x=>(x.name+' '+x.id).toLowerCase().includes(query)),signature=JSON.stringify([lang,selected,query,rows,!!state.continuous?.enabled,busy,modeBusy]);
 if(signature===listSignature){paintSelection();return;}listSignature=signature;$('list').replaceChildren();
 if(!rows.length){const p=document.createElement('p');p.className='subtle';p.textContent=t(query?'noMatch':'noChats');$('list').append(p);}
 for(const row of rows){
  const label=document.createElement('div');label.className='chat';const radio=document.createElement('input');radio.type='radio';radio.name='chat';radio.value=row.id;radio.checked=row.id===selected;radio.disabled=!!state.continuous?.enabled;radio.setAttribute('aria-label',row.name);
  const copy=document.createElement('div');copy.className='chatcopy';const name=document.createElement('div');name.className='chatname';name.textContent=row.name;const meta=document.createElement('div');meta.className='chatmeta';meta.textContent=(row.cwd?row.cwd+' · ':'')+t('sessionId')+' '+row.id+(row.updatedAt?' · '+new Date(row.updatedAt*1000).toLocaleDateString(locale()):'');copy.append(name,meta);
  const badge=document.createElement('span');badge.className='badge'+(row.terminal?.state==='running'?'':' neutral');badge.textContent=terminalLabels[lang][row.terminal?.state]||t('choose');
  radio.addEventListener('change',()=>{manualSelection=true;selected=row.id;try{localStorage.setItem('reset-selected-thread',selected);}catch{}paintList();});
  copy.addEventListener('click',()=>{if(!radio.disabled){radio.checked=true;radio.dispatchEvent(new Event('change'));}});
  label.append(radio,copy,badge,actionButtons(terminalItem(row)));$('list').append(label);
 }
 $('more').hidden=!state.has_more;paintSelection();
}
function paintTerminals(){
 const inv=state?.terminal_inventory||{},rows=inv.items||[];
 $('terminal-check').disabled=terminalChecking;$('terminal-check').textContent=t(terminalChecking?'terminalChecking':'terminalCheck');$('terminal-end-background').disabled=terminalChecking||busy;
 $('terminal-summary').textContent=!inv.checked_at?t('terminalNotChecked'):!rows.length?t('terminalNone'):t('terminalCount').replace('{n}',rows.length)+new Date(inv.checked_at*1000).toLocaleTimeString(locale(),{hour12:false});
 $('terminal-list').replaceChildren();
 for(const item of rows){
  const row=document.createElement('div');row.className='terminal-row';const copy=document.createElement('div');copy.className='terminal-copy';const name=document.createElement('strong');name.textContent=item.thread_id?item.name:t('unknownChat');
  const meta=document.createElement('span');meta.className='subtle';const host=item.target_type==='managed'?'hostManaged':{psmux:'hostPsmux',vscode:'hostVscode',console:'hostConsole'}[item.host_kind]||'hostUnknown';
  meta.textContent=t(host)+' · '+t(item.connection==='background'?'terminalBackground':item.connection==='attached'?'terminalAttached':'terminalUnknown')+(item.pid?' · PID '+item.pid:'')+(item.outside_pids?.length?(lang==='zh'?' · 其他终端 PID ':' · Other terminal PID ')+item.outside_pids.join(', '):'');copy.append(name,meta);if(item.thread_id){const id=document.createElement('span');id.className='subtle';id.textContent=t('sessionId')+' '+item.thread_id;copy.append(id);}
  row.append(copy,actionButtons(item));$('terminal-list').append(row);
 }
}
async function checkTerminals(){if(terminalChecking)return;terminalChecking=true;paintTerminals();try{const r=await api('/api/terminal/check',{});if(state&&(!state.terminal_inventory?.checked_at||r.terminal_inventory.checked_at>=state.terminal_inventory.checked_at))state.terminal_inventory=r.terminal_inventory;}catch(e){notice(errorText(e),true);}finally{terminalChecking=false;paintTerminals();}}
async function checkTerminalsAfterAction(){while(terminalChecking)await new Promise(resolve=>setTimeout(resolve,25));await checkTerminals();}
async function loadAfterAction(){if(pendingLoad)await pendingLoad;await load();}
function markClosed(tid){if(!state||!tid)return;const row=(state.threads||[]).find(x=>x.id===tid);if(row)row.terminal={state:'closed',can_close:false};const inv=state.terminal_inventory||{};state.terminal_inventory={...inv,items:(inv.items||[]).filter(x=>x.thread_id!==tid),checked_at:Date.now()/1000};paintList();paintTerminals();}
async function reconnectTerminal(item){
 if(busy||!item)return;if(typeof item==='string')item={thread_id:item};busy=true;actionNotice(t('opening'));
 try{paintSelection();paintTerminals();paintList();let r=await api('/api/terminal/open',{thread_id:item.thread_id,model:$('model').value,effort:$('effort').value});await loadAfterAction();actionNotice(t(r.action==='revealed_existing'?'revealedExisting':r.action==='already_attached'?'alreadyAttached':r.action==='focused_existing'?'focusedExisting':r.action==='reused'?'reuseDone':r.action==='awaiting_viewer'?'viewerWait':'openDone'));await checkTerminalsAfterAction();}
 catch(e){actionNotice(e.name==='AbortError'?t('openUnknown'):errorText(e),true);}finally{busy=false;paintSelection();paintTerminals();paintList();}
}
async function endTerminal(item){
 if(busy||modeBusy||!item.can_close)return;
 const confirmation=t('terminalConfirm').replace('{title}',item.name).replace('{pid}',item.pid||'')+(item.thread_id?'\n\n'+t('sessionId')+': '+item.thread_id:'')+(item.outside_pids?.length?(lang==='zh'?'\n\n只结束本软件登记的终端。其他终端仍在运行，PID：':'\n\nOnly this managed terminal will end. Other terminals remain running, PID: ')+item.outside_pids.join(', '):'');if(!window.confirm(confirmation))return;
 busy=true;paintSelection();paintTerminals();paintList();
 try{const r=await api('/api/terminal/close',{thread_id:item.thread_id,close_token:item.close_token,confirmed:true});if(pendingLoad)await pendingLoad;markClosed(r.thread_id);await load();await checkTerminalsAfterAction();notice(t('terminalClosed'));}
 catch(e){notice(errorText(e),true);}finally{busy=false;paintSelection();paintTerminals();paintList();}
}
async function endBackground(){
 if(busy)return;busy=true;paintTerminals();paintList();
 try{const plan=await api('/api/terminal/background/prepare',{});if(!plan.items.length){notice(t('bulkNone'));return;}
 const list=plan.items.map(item=>'• '+item.name+' · PID '+(item.pid||'—')+' · '+t('sessionId')+' '+item.thread_id).join('\n');if(!window.confirm(t('bulkConfirm').replace('{list}',list)))return;
 const r=await api('/api/terminal/background/close',{plan_id:plan.plan_id,confirmed:true});await loadAfterAction();await checkTerminalsAfterAction();notice(t('bulkDone').replace('{closed}',r.closed.length).replace('{skipped}',r.skipped.length));}
 catch(e){notice(errorText(e),true);}finally{busy=false;paintTerminals();paintList();}
}
function fillEfforts(value=''){const model=(state?.models||[]).find(x=>x.model===$('model').value);$('effort').replaceChildren(new Option(t('defaultEffort'),''));const names=lang==='zh'?{minimal:'最少',low:'较低',medium:'中等',high:'较高',xhigh:'更高',max:'最高',ultra:'极高'}:{};for(const effort of model?.efforts||[])$('effort').add(new Option(names[effort]?names[effort]+' · '+effort:effort,effort));$('effort').disabled=!model||!(model.efforts||[]).length;$('effort').value=value;if(!$('effort').value)$('effort').value='';}
function fillSettings(values){const chosen=$('model').value,effort=$('effort').value;$('model').replaceChildren(new Option(t('defaultModel'),''));for(const model of state?.models||[])$('model').add(new Option(model.name,model.model));$('model').value=chosen||'';fillEfforts(effort);$('proxy-host').value=values.proxy_host||'';$('proxy-port').value=values.proxy_port||'';}
function paintSettings(){const s=state?.settings;if(!s)return;const model=null,proxy=s.effective.proxy_url||(lang==='zh'?'跟随系统':'System settings'),workspace=state.working_directory||(lang==='zh'?'所有工作目录':'All workspaces');$('settings-summary').textContent=proxy;$('proxy-summary').textContent=t('workingDir')+': '+workspace+' · '+t('proxy')+': '+proxy;$('models-help').textContent=state.models_error?t('modelsUnavailable'):'';$('models-help').hidden=!state.models_error;const signature=JSON.stringify([lang,s.values,state.models]);if(!settingsDirty&&!settingsSaving&&signature!==settingsSignature){fillSettings(s.values);settingsSignature=signature;}}
async function saveSettings(values){if(!state?.settings){notice(t('waitSettings'),true);return;}if(settingsSaving)return;settingsSaving=true;$('settings-save').disabled=true;$('settings-defaults').disabled=true;$('settings-status').textContent=t('saving');$('settings-status').classList.remove('error');try{const r=await api('/api/settings',values);state.settings=r.settings;settingsDirty=false;fillSettings(r.settings.values);$('settings-status').textContent=t('saved');notice(t('saveNotice'));}catch(e){$('settings-status').textContent=errorText(e);$('settings-status').classList.add('error');}finally{settingsSaving=false;$('settings-save').disabled=false;$('settings-defaults').disabled=false;paintSettings();}}
function paintMode(){const m=state?.continuous||{enabled:false,phase:'idle'},phase=m.phase||'idle',active=!!m.enabled||phase==='cancelling',row=currentThread();$('mode-phase').textContent=phases[lang][phase]||phase;$('mode-phase').classList.toggle('active',!!m.enabled);$('continuous-start').disabled=modeBusy||active||!row||['external','uncertain','conflict'].includes(row.terminal?.state);for(const id of ['auto-goal','auto-update','command-text'])$(id).disabled=active||modeBusy;if(active){$('auto-goal').checked=m.auto_goal!==false;$('auto-update').checked=m.auto_update!==false;if(typeof m.command==='string')$('command-text').value=m.command;}$('continuous-cancel').disabled=!(m.enabled||phase==='cancelling'||modeBusy||phase==='needs_attention');$('recovery-count').disabled=active||modeBusy;$('shutdown-enabled').disabled=active||modeBusy;$('model').disabled=active||modeBusy;$('effort').disabled=active||modeBusy||!$('model').value;if(active)$('shutdown-enabled').checked=!!m.shutdown_enabled;if(active&&m.recovery_limit!==undefined)$('recovery-count').value=String(m.recovery_limit);let text=m.reason?(reasons[lang][m.reason]||t('genericError')):t('ready');if(!active&&row?.terminal?.state==='external')text=t('externalModeHelp');else if(!active&&['uncertain','conflict'].includes(row?.terminal?.state))text=t('targetUnknown');else if(m.data_warning)text=t('dataFailed');else if(phase==='running')text=t('keepAwake')+' · '+(m.title||row?.name||'');else if(phase==='waiting_quota')text=t('keepAwake')+' · '+(m.wait_until?countdown(m.wait_until-Date.now()/1000):t('noReset'));if(phase==='awaiting_idle')text=lang==='zh'?'所选额度轮次已耗尽，等待终端空闲后开始关机倒计时。':'Selected rounds exhausted. Waiting for an idle terminal before shutdown.';if(phase==='shutdown_pending')text=(lang==='zh'?'将在 ':'Shutdown in ')+Math.max(0,Math.ceil((m.shutdown_at||0)-Date.now()/1000))+(lang==='zh'?' 秒后关机，可点击取消。':' seconds. Select Cancel to stop.');if(phase==='cancelled')text=t('modeCancelled');if(m.last_error&&phase==='needs_attention')text=m.last_error;paintShutdownHelp();$('mode-message').textContent=text;$('mode-count').textContent=m.thread_id?t('progress').replace('{done}',m.recoveries_done||0).replace('{limit}',m.recovery_limit||0):'';}
function paintShutdownHelp(){const n=Number($('recovery-count').value),on=$('shutdown-enabled').checked;$('shutdown-help').textContent=lang==='zh'?(n===0?'不等待额度恢复，当前额度耗尽后':'等待 '+n+' 次额度恢复，再用完最后一轮额度后')+(on?'等待终端空闲，倒计时 60 秒自动关机。':'结束自动推进，不关机。'):(n===0?'No recovery: when current quota runs out, ':'Wait for '+n+' recoveries, then exhaust the final round: ')+(on?'wait for idle, then shut down after a cancellable 60-second countdown.':'stop automation without shutting down.');}
function applyLanguage(){document.documentElement.lang=lang==='zh'?'zh-CN':'en';$('language').value=lang;document.querySelectorAll('[data-i18n]').forEach(e=>{if(strings[lang][e.dataset.i18n])e.textContent=t(e.dataset.i18n);});$('search').placeholder=t('search');$('search').setAttribute('aria-label',t('search'));$('proxy-host').placeholder=t('defaultHost');$('proxy-port').placeholder=t('defaultPort');$('recovery-help').textContent=t('recoveryHelp');for(const option of $('recovery-count').options)option.textContent=option.value==='0'?t('zeroRecoveries'):option.value+(lang==='zh'?' 次':'');$('settings-status').textContent=t(settingsDirty?'unsaved':'blankHelp');if(state){const draft=settingsDirty?{model:$('model').value,effort:$('effort').value,proxy_host:$('proxy-host').value,proxy_port:$('proxy-port').value}:null;if(draft)fillSettings(draft);paintQuota(state.quota||{});paintList();paintSettings();paintTerminals();}else{$('connection').textContent=t('connecting');$('selectedname').textContent=t('selecting');$('freshness').textContent=t('unread');$('settings-summary').textContent=t('defaultShort');fillSettings({});paintMode();}notice('');}
function load(){if(pendingLoad)return pendingLoad;pendingLoad=(async()=>{try{const next=await api('/api/state'),previous=state?.terminal_inventory;if(previous?.checked_at&&(!next.terminal_inventory?.checked_at||previous.checked_at>next.terminal_inventory.checked_at))next.terminal_inventory=previous;state=next;if(!globalThis.resetPreferencesLoaded){const pref=state.preferences||{};if(!selected&&pref.thread_id)selected=pref.thread_id;if(pref.recovery_limit!==undefined){const value=String(pref.recovery_limit);if(!Array.from($('recovery-count').options).some(o=>o.value===value))$('recovery-count').add(new Option(value,value));$('recovery-count').value=value;}try{if(!localStorage.getItem('reset-language')&&pref.language){lang=pref.language;applyLanguage();}}catch{}if(typeof state.continuous?.command==='string')$('command-text').value=state.continuous.command;$('auto-goal').checked=state.continuous?.auto_goal!==false;$('auto-update').checked=state.continuous?.auto_update!==false;globalThis.resetPreferencesLoaded=true;}chooseDefault();paintQuota(state.quota||{});paintList();paintSettings();paintTerminals();globalThis.ResetSetup?.render(state,lang);if(state.error&&!busy&&!modeBusy&&Date.now()>actionNoticeUntil)notice(globalThis.ResetSetup?.error(state.error_code)||t('dataFailed'),true);}catch{if(Date.now()>actionNoticeUntil)notice(t('loadFailed'),true);}finally{pendingLoad=null;}})();return pendingLoad;}
$('language').addEventListener('change',()=>{lang=$('language').value;try{localStorage.setItem('reset-language',lang);}catch{}applyLanguage();if(state)globalThis.ResetSetup?.render(state,lang);});
$('search').addEventListener('input',()=>state&&paintList());
$('settings-form').addEventListener('input',()=>{settingsDirty=true;$('settings-status').textContent=t('unsaved');$('settings-status').classList.remove('error');});
$('model').addEventListener('change',()=>{fillEfforts();});
$('settings-form').addEventListener('submit',e=>{e.preventDefault();saveSettings({model:'',effort:'',proxy_host:$('proxy-host').value,proxy_port:$('proxy-port').value});});
$('settings-defaults').addEventListener('click',()=>saveSettings({model:'',effort:'',proxy_host:'',proxy_port:''}));
$('refresh').addEventListener('click',async()=>{$('refresh').disabled=true;try{await api('/api/refresh',{});await load();if(!state.error)notice(t('refreshDone'));}catch(e){notice(errorText(e),true);}finally{$('refresh').disabled=false;}});
$('more').addEventListener('click',async()=>{$('more').disabled=true;try{await api('/api/more',{});await load();}catch(e){notice(errorText(e),true);}finally{$('more').disabled=false;}});
$('view').addEventListener('click',()=>currentThread()&&reconnectTerminal(terminalItem(currentThread())));
async function startContinuous(){if(modeBusy||!currentThread())return;modeBusy=true;cancelRequested=false;actionNotice(t('handlingStart'));paintMode();try{const r=await api('/api/continuous/start',{thread_id:selected,recovery_limit:Number($('recovery-count').value),shutdown:$('shutdown-enabled').checked,model:$('model').value,effort:$('effort').value,command:$('command-text').value,auto_goal:$('auto-goal').checked,auto_update:$('auto-update').checked});state.continuous=r.continuous;if(cancelRequested){const cancelled=await api('/api/continuous/cancel',{});state.continuous=cancelled.continuous;}actionNotice(cancelRequested?t('modeCancelled'):r.continuous.messages_sent>0?(lang==='zh'?'推进命令已发送到所选会话。':'Continuation message sent to the selected conversation.'):r.continuous.phase==='waiting_quota'?(lang==='zh'?'额度已耗尽，正在等待恢复；尚未发送命令。':'Quota exhausted; waiting for recovery. No message sent yet.'):r.continuous.data_warning?(lang==='zh'?'额度暂不可确认，命令尚未发送；会在确认后继续。':'Quota is unconfirmed. Message not sent yet.'): (lang==='zh'?'正在向终端发送，请等待发送结果。':'Sending to the terminal; waiting for confirmation.'));}catch(e){actionNotice(errorText(e),true);}finally{modeBusy=false;paintMode();await load();}}
$('continuous-start').addEventListener('click',()=>startContinuous());
$('continuous-cancel').addEventListener('click',async()=>{cancelRequested=true;try{const r=await api('/api/continuous/cancel',{});if(state)state.continuous=r.continuous;paintMode();notice(t('modeCancelled'));}catch(e){notice(errorText(e),true);}});
$('recovery-count').addEventListener('change',paintShutdownHelp);$('shutdown-enabled').addEventListener('change',paintShutdownHelp);
$('terminal-check').addEventListener('click',checkTerminals);
$('terminal-end-background').addEventListener('click',endBackground);
window.addEventListener('reset-setup-changed',()=>load());applyLanguage();load().then(()=>checkTerminals());setInterval(load,3000);setInterval(()=>{if(state&&!busy&&!terminalChecking)checkTerminals();},5000);setInterval(()=>{if(state){paintQuota(state.quota||{});paintMode();}},1000);
})();
