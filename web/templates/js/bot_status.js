/**
 * Bot Status Reader Module (Admin Only)
 */

let botStatusInterval = null;

async function updateBotStatusUI() {
    const panel = document.getElementById("bot-status-panel");
    if (!panel || panel.style.display === "none") {
        if (botStatusInterval) {
            clearInterval(botStatusInterval);
            botStatusInterval = null;
        }
        return;
    }

    try {
        const token = sessionStorage.getItem("gex_auth_token");
        const response = await fetch('/api/bot_status', {
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await safeJsonParse(response);
        if (!data) throw new Error("Parsed data is null or invalid json");
        renderBotStatus(data);
        
        if (!botStatusInterval) {
            botStatusInterval = setInterval(updateBotStatusUI, 10000); // Poll every 10s
        }
    } catch (e) {
        console.error("Failed to fetch bot status:", e);
        document.getElementById("bot-status-content").innerHTML = `
            <div style="color:var(--accent-red); padding:10px; text-align:center;">
                Connection Error
            </div>
        `;
    }
}

function renderBotStatus(data) {
    const container = document.getElementById("bot-status-content");
    let html = "";
    
    const rlOpen = Object.values(data.open_positions.rl || {});
    const gbmOpen = Object.values(data.open_positions.gbm || {});
    
    // SECTION: OPEN POSITIONS
    html += `<div class="ms-cause-title" style="margin-top:0;">Open Positions</div>`;
    
    if (rlOpen.length === 0 && gbmOpen.length === 0) {
        html += `<div style="text-align:center; padding: 15px; color: var(--text-dim); font-size:12px; background: rgba(255,255,255,0.02); border-radius: 4px;">NO TRADES OPEN</div>`;
    } else {
        html += `<div style="display:flex; flex-direction:column; gap:8px; margin-bottom:15px;">`;
        
        // Render RL Positions
        for (const pos of rlOpen) {
            const entryTime = new Date(pos.entry_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            const dirColor = pos.direction === 'LONG' ? 'var(--accent-green)' : 'var(--accent-red)';
            html += `
                <div style="background: rgba(30,30,35,0.8); border-left: 3px solid ${dirColor}; padding: 8px; border-radius: 0 4px 4px 0;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                        <span style="font-weight:bold; font-size:13px;"><span style="color:#1E90FF; font-size:10px; vertical-align:super;">[RL]</span> ${pos.ticker} ${pos.direction}</span>
                        <span style="color:var(--text-dim); font-size:11px;">${entryTime}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'Roboto Mono';">
                        <span>Strike: ${pos.strike.toFixed(0)}</span>
                        <span>$${pos.entry_premium.toFixed(2)}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:11px; margin-top:4px;">
                        <span style="color:var(--text-dim);">Conf: ${(pos.confidence*100).toFixed(0)}%</span>
                        <span style="color:var(--text-dim);">MAE: ${(pos.mae*100).toFixed(1)}%</span>
                    </div>
                </div>
            `;
        }
        
        // Render GBM Trackers
        for (const tr of gbmOpen) {
            const entryTime = new Date(tr.entry_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            const dirColor = tr.direction === 'LONG' ? 'var(--accent-green)' : 'var(--accent-red)';
            html += `
                <div style="background: rgba(30,30,35,0.8); border-left: 3px solid ${dirColor}; padding: 8px; border-radius: 0 4px 4px 0;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                        <span style="font-weight:bold; font-size:13px;"><span style="color:#FFD700; font-size:10px; vertical-align:super;">[GBM]</span> ${tr.ticker} ${tr.direction}</span>
                        <span style="color:var(--text-dim); font-size:11px;">${entryTime}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:12px; font-family:'Roboto Mono';">
                        <span>Spot: ${tr.entry_price.toFixed(2)}</span>
                        <span style="color:var(--text-dim);">Conf: ${(tr.confidence*100).toFixed(0)}%</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:10px; margin-top:4px;">
                        <span style="color:var(--accent-green);">TP: ${tr.target_price.toFixed(2)}</span>
                        <span style="color:var(--accent-red);">SL: ${tr.stop_price.toFixed(2)}</span>
                    </div>
                </div>
            `;
        }
        html += `</div>`;
    }

    // SECTION: HISTORY
    html += `<div class="ms-cause-title" style="margin-top:15px;">Today's Closed Trades</div>`;
    
    // Flatten and sort history by exit_time
    const rlHist = data.history.rl || [];
    const gbmHist = data.history.gbm || [];
    
    // Backwards compat inject model
    rlHist.forEach(t => t.model = 'RL');
    
    const combinedHistory = [...rlHist, ...gbmHist];
    combinedHistory.sort((a, b) => new Date(b.exit_time) - new Date(a.exit_time)); // Latest first
    
    let totalPnl = 0;
    let rlPnl = 0;
    let rlTradesCount = 0;
    
    if (combinedHistory.length === 0) {
        html += `<div style="text-align:center; padding: 15px; color: var(--text-dim); font-size:12px; background: rgba(255,255,255,0.02); border-radius: 4px;">NO CLOSED TRADES TODAY</div>`;
    } else {
        html += `<div style="display:flex; flex-direction:column; gap:6px;">`;
        for (const t of combinedHistory) {
            const exitTime = new Date(t.exit_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            const isWin = t.pnl_pct >= 0;
            const resColor = isWin ? 'var(--accent-green)' : 'var(--accent-red)';
            const tagColor = t.model === 'RL' ? '#1E90FF' : '#FFD700';
            
            if(t.model === 'RL') {
                rlPnl += (t.pnl_dollars || 0);
                rlTradesCount++;
            }
            
            html += `
                <div style="background: rgba(30,30,35,0.5); padding: 6px; border-radius: 4px; display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; flex-direction:column;">
                        <span style="font-size:12px; font-weight:bold;"><span style="color:${tagColor};">[${t.model}]</span> ${t.ticker} ${t.direction}</span>
                        <span style="font-size:10px; color:var(--text-dim);">${exitTime} | ${(t.hold_minutes || 0).toFixed(0)}m</span>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:${resColor}; font-weight:bold; font-size:13px; font-family:'Roboto Mono';">${(isWin?'+':'')}${(t.pnl_pct*100).toFixed(1)}%</div>
                        ${t.model === 'RL' ? `<div style="font-size:10px; color:var(--text-dim);">${t.exit_reason || ''}</div>` : ''}
                    </div>
                </div>
            `;
        }
        html += `</div>`;
    }
    
    if (rlTradesCount > 0) {
        const netColor = rlPnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
        html += `
            <div style="margin-top: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 4px; text-align:center;">
                <div style="font-size:10px; color:var(--text-dim);">RL NET DAILY P&L (${rlTradesCount} trades)</div>
                <div style="font-size:16px; font-weight:bold; color:${netColor}; font-family:'Roboto Mono';">$${rlPnl.toFixed(2)}</div>
            </div>
        `;
    }

    container.innerHTML = html;
}
