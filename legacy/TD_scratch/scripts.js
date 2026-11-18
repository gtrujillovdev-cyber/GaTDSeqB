        async function fetchSystem() {
            try {
                let res = await fetch('/api/system');
                let data = await res.json();
                document.getElementById('sys-cpu').innerText = `${data.cpu}%`;
                document.getElementById('sys-ram').innerText = `${data.ram}%`;
                document.getElementById('sys-temp').innerText = `${data.temp}°C`;
            } catch(e) {}
        }
        
        let globalPrices = { 'BTC': 0, 'ETH': 0, 'HYPE': 0 };
        let currentFleet = null;

        async function fetchPrices() {
            try {
                let res = await fetch('https://api.binance.com/api/v3/ticker/price?symbols=%5B%22BTCUSDT%22,%22ETHUSDT%22,%22HYPEUSDT%22%5D');
                if (!res.ok) {
                    // Fallback just for BTC if HYPE fails
                    res = await fetch('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT');
                    let data = await res.json();
                    let p = parseFloat(data.price);
                    globalPrices['BTC'] = p;
                    updateBtcHeader(p);
                } else {
                    let data = await res.json();
                    for (let d of data) {
                        if (d.symbol === 'BTCUSDT') {
                            globalPrices['BTC'] = parseFloat(d.price);
                            updateBtcHeader(globalPrices['BTC']);
                        } else if (d.symbol === 'ETHUSDT') {
                            globalPrices['ETH'] = parseFloat(d.price);
                        } else if (d.symbol === 'HYPEUSDT') {
                            globalPrices['HYPE'] = parseFloat(d.price);
                        }
                    }
                }
                
                if (currentFleet) {
                    renderFleet(currentFleet, false); // false means do not update UI completely? Actually just re-render is fine.
                }
            } catch(e) {}
        }
        
        let lastBtcHeaderPrice = 0;
        function updateBtcHeader(price) {
            let priceEl = document.getElementById('btc-price');
            priceEl.innerText = `$${price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (price > lastBtcHeaderPrice && lastBtcHeaderPrice !== 0) { priceEl.style.color = '#00ff00'; }
            else if (price < lastBtcHeaderPrice) { priceEl.style.color = '#ff0000'; }
            lastBtcHeaderPrice = price;
        }
        
        async function fetchFnG() {
            try {
                let res = await fetch('https://api.alternative.me/fng/?limit=1');
                let data = await res.json();
                let val = parseInt(data.data[0].value);
                let fngEl = document.getElementById('fng-index');
                fngEl.innerText = `${val} (${data.data[0].value_classification})`;
                if (val >= 60) { fngEl.style.color = '#00ff00'; }
                else if (val <= 40) { fngEl.style.color = '#ff0000'; }
                else { fngEl.style.color = '#ffb200'; }
            } catch(e) {}
        }

        let lastNetWorth = 0;
        let lastPortfolioHtml = '<div style="text-align:center; color:#FFCC00; margin-top:20px; font-size:11px;">CARGANDO DATOS...</div>';
        let priceFallbackCache = {};
        
        async function fetchPortfolio() {
            try {
                let res = await fetch('/api/portfolio');
                let data = await res.json();
                let activos = data.activos || {};
                let prices = data.prices || {};
                let changes = data.changes || {};
                
                let totalValue = 0;
                let totalPnl = 0;
                let totalDailyChangeUSD = 0;
                let pfHtml = '';
                
                let symbolOrder = ['BTC', 'MSTR', 'ETH', 'PEPE'];
                for (let symbol of symbolOrder) {
                    if (!activos[symbol]) continue;
                    let asset = activos[symbol];
                    let type = asset.type || 'spot';
                    let amount = asset.amount;
                    let currentPrice = 0;
                    
                    let priceChange24h = changes[symbol] || 0;
                    if (prices[symbol]) { currentPrice = prices[symbol]; } 
                    else if (symbol === 'USDT' || symbol === 'USDC') { currentPrice = 1; }
                    else {
                        try {
                            let priceRes = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${symbol}USDT`);
                            if (priceRes.ok) {
                                let priceData = await priceRes.json();
                                currentPrice = parseFloat(priceData.lastPrice);
                                priceChange24h = parseFloat(priceData.priceChange);
                                priceFallbackCache[symbol] = currentPrice;
                                priceFallbackCache[symbol+'_change'] = priceChange24h;
                            } else {
                                throw new Error("Binance Rate Limit / Error");
                            }
                        } catch(e) {
                            if (priceFallbackCache[symbol]) {
                                currentPrice = priceFallbackCache[symbol];
                                priceChange24h = priceFallbackCache[symbol+'_change'] || 0;
                            }
                        }
                    }
                    totalDailyChangeUSD += (priceChange24h * amount);

                    
                    let pnlStr = '';
                    if (type === 'spot') {
                        let value = amount * currentPrice;
                        totalValue += value;
                        let extraInfo = `<span>${amount} u.</span>`;
                        if (asset.entry_price) {
                            let pnl = (currentPrice - asset.entry_price) * amount;
                            totalPnl += pnl;
                            let pColor = pnl >= 0 ? 'val-green' : 'val-red';
                            pnlStr = `<span class="${pColor}">${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>`;
                            extraInfo = `
                                <div style="display:flex; flex-direction:column; line-height:1.4;">
                                    <span>${amount} u.</span>
                                    <span>Entry: $${asset.entry_price.toLocaleString(undefined, {maximumFractionDigits: 8})}</span>
                                </div>
                            `;
                        } else {
                            pnlStr = `<span style="color:#ffffff;">Spot</span>`;
                        }
                        
                        pfHtml += `
                        <div class="row" style="display:flex; flex-direction:column; margin-bottom: 12px; border-bottom: 1px dotted #151515; padding-bottom:10px;">
                            <div style="display:flex; justify-content:space-between; width:100%; margin-bottom:4px;">
                                <span style="font-weight:bold;">${symbol}</span>
                                <span>$${currentPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; width:100%; font-size:12px; color:#FFCC00; align-items:center;">
                                ${extraInfo}
                                <div>${pnlStr}</div>
                            </div>
                        </div>`;
                        
                    } else if (type === 'long') {
                        let pnl = (currentPrice - asset.entry_price) * amount;
                        totalPnl += pnl;
                        totalValue += asset.margin + pnl;
                        let pColor = pnl >= 0 ? 'val-green' : 'val-red';
                        pnlStr = `<span class="${pColor}">${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>`;
                        
                        let extraInfo = `
                            <div style="display:flex; flex-direction:column; line-height:1.4;">
                                <span>Margin: $${asset.margin.toLocaleString(undefined, {maximumFractionDigits: 2})}</span>
                                <span>E: $${asset.entry_price.toLocaleString(undefined, {maximumFractionDigits: 8})}${asset.liq_price ? ' <span style="margin:0 4px;">|</span> <span style="color:#ff6b6b">Liq: $'+asset.liq_price.toLocaleString(undefined, {maximumFractionDigits: 8})+'</span>' : ''}</span>
                            </div>
                        `;
                        
                        pfHtml += `
                        <div class="row" style="display:flex; flex-direction:column; margin-bottom: 12px; border-bottom: 1px dotted #151515; padding-bottom:10px;">
                            <div style="display:flex; justify-content:space-between; width:100%; margin-bottom:4px;">
                                <span style="font-weight:bold; color:#00ff00;">${symbol} LONG</span>
                                <span>$${currentPrice.toLocaleString(undefined, {minimumFractionDigits: 4, maximumFractionDigits: 8})}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; width:100%; font-size:12px; color:#FFCC00; align-items:center;">
                                ${extraInfo}
                                <div>${pnlStr}</div>
                            </div>
                        </div>`;
                    }
                }
                
                let nwEl = document.getElementById('net-worth');
                let dailyPct = totalValue > 0 ? (totalDailyChangeUSD / (totalValue - totalDailyChangeUSD)) * 100 : 0;
                let dailySign = totalDailyChangeUSD >= 0 ? '+' : '';
                nwEl.innerHTML = `$${totalValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} <span style="font-size:10px; color:${totalDailyChangeUSD >= 0 ? '#00ff00' : '#ff4444'};">(${dailySign}${dailyPct.toFixed(2)}%)</span>`;
                if (totalValue > lastNetWorth && lastNetWorth !== 0) { nwEl.className = 'val-green'; }
                else if (totalValue < lastNetWorth) { nwEl.className = 'val-red'; }
                lastNetWorth = totalValue;
                
                let tpnlColor = totalPnl >= 0 ? 'val-green' : 'val-red';
                let tpnlStr = totalPnl >= 0 ? '+' : '';
                
                pfHtml += `
                <div style="margin-top: 15px; text-align: center;">
                    <div style="font-size:11px; color:#FFCC00; margin-bottom:5px;">NET WORTH EST.</div>
                    <div style="font-size:22px; font-weight:bold; color:#00ff00; margin-bottom:5px;">$${totalValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                    <div class="${tpnlColor}" style="font-size:14px; font-weight:bold; background-color: rgba(0,0,0,0.2); padding: 4px 8px; border-radius: 4px; display: inline-block;">
                        ${tpnlStr}$${Math.abs(totalPnl).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </div>
                </div>`;
                
                lastPortfolioHtml = pfHtml;
                
                let pfBody = document.getElementById('portfolio-body');
                if (pfBody) {
                    pfBody.innerHTML = pfHtml;
                }
                
            } catch(e) {}
        }

        function renderFleet(fleet) {
            try {
                let htmlGrid = '';
                let globalEquity = 0.0;
                let globalUnrealizedPnl = 0;
                let activeTradesCount = 0;
                let totalHistoricalTrades = 0;
                let activeBotsCount = 0;
                
                for (const asset of ['BTC', 'ETH', 'HYPE']) {
                    let assetGrid = `<div class="bot-column"><h2>${asset}</h2>`;
                    
                    if (!fleet[asset]) continue;
                    
                    for (const tf of ['5m', '15m', '1h', '4h', '1d']) {
                        const state = fleet[asset][tf];
                        if (!state) continue;
                        activeBotsCount++;
                        globalEquity += state.bank || 10000.0;
                        
                        let badgeClass = 'status-offline';
                        let badgeText = 'OFFLINE';
                        if (state.trades_count) totalHistoricalTrades += state.trades_count / 2;
                        if (state.status === 'IN_TRADE') { badgeClass = 'status-active'; badgeText = 'IN TRADE'; }
                        else if (state.status === 'IDLE') { badgeClass = 'status-idle'; badgeText = 'IDLE'; }
                        
                        let tdColor = state.td_count > 0 ? 'val-red' : (state.td_count < 0 ? 'val-green' : '');
                        
                        if (state.status !== 'IN_TRADE') {
                            let roi = state.bank ? ((state.bank - 10000) / 10000) * 100 : 0;
                            let rColor = roi >= 0 ? '#00ff00' : '#ff0000';
                            let rSign = roi > 0 ? '+' : '';
                            let roiStr = state.bank ? `<span style="color:${rColor}; font-size:14px; font-weight:bold;">$${state.bank.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits:2})} <span style="font-size:11px; font-weight:normal;">(${rSign}${roi.toFixed(2)}%)</span></span>` : '';
                            
                            assetGrid += `
                                <div class="bot-card tf-card" style="margin-bottom: 0px; padding: 0px 10px; height: 45px; display: grid; grid-template-columns: 35px 1fr auto; align-items: center; gap: 8px; overflow: hidden; white-space: nowrap;  flex-direction: row;">
                                        <span style="font-size: 10px; font-weight: bold; color: #ffb200; text-align: left; display: block;">[${tf}]</span>
                                        <div style="white-space: nowrap; text-align: left; display: block;">${roiStr}</div>
                                        <div style="display:flex; gap:10px; align-items:center; justify-content: flex-end;">
                                            <span style="font-size: 11px; color: #fff;">TD: <span class="${tdColor}" style="display: inline-block; width: 22px; text-align: right;">${state.td_count !== undefined ? state.td_count : '--'}</span></span>
                                            <span class="status-badge ${badgeClass}" style="width: 35px; text-align: center;">${badgeText}</span>
                                        </div>
                                </div>
                            `;
                            continue;
                        }
                        
                        assetGrid += `
                            <div class="bot-card active-trade-card">
                                <div class="bot-header">
                                    <span>[ ${tf} ]</span>
                                    <span class="status-badge ${badgeClass}">${badgeText}</span>
                                </div>
                                <div class="bot-body">
                                    
                                    <div class="trade-stats-grid">
                                    <div class="row">
                                        <span class="label" style="font-size:11px;">Bank/ROI</span>
                                        <span class="value val-green" style="font-size: 13px;">
                                            $${state.bank ? state.bank.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '--'}
                                            ${state.bank ? (function(){
                                                let roi = ((state.bank - 10000) / 10000) * 100;
                                                let rColor = roi >= 0 ? '#00ff00' : '#ff0000';
                                                let rSign = roi >= 0 ? '+' : '';
                                                return `<span style="font-size:10px; color:${rColor};">(${rSign}${roi.toFixed(1)}%)</span>`;
                                            })() : ''}
                                        </span>
                                    </div>
                                    <div class="row"><span class="label" style="font-size:11px;">TD Count</span><span class="value ${tdColor}">${state.td_count !== undefined ? state.td_count : '--'}</span></div>
                                    <div class="row"><span class="label" style="font-size:11px;">Position</span><span class="value ${state.position==='BUY'?'val-green':(state.position==='SELL'?'val-red':'')}">${state.position || 'NONE'}</span></div>
                                    <div class="row"><span class="label" style="font-size:11px;">Invest/Lev</span><span class="value">${state.size_usd ? '$'+state.size_usd.toLocaleString(undefined, {maximumFractionDigits:0}) + (state.leverage ? ' (<span style="color:#ffffff">x'+state.leverage.toFixed(1)+'</span>)' : '') : '--'}</span></div>
                                    <div class="row"><span class="label" style="font-size:11px;">Entry</span><span class="value">${state.entry_price ? '$'+state.entry_price.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : '--'}</span></div>
                                    <div class="row"><span class="label" style="font-size:11px;">Stop</span><span class="value">${state.stop_loss ? '$'+state.stop_loss.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : '--'}</span></div>
                                    <div class="row"><span class="label" style="font-size:11px;">Take Pr.</span><span class="value">${state.take_profit ? '$'+state.take_profit.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : '--'}</span></div>
                                    <div class="row"><span class="label" style="font-size:11px;">Risk Exp.</span><span class="value">${state.risk_usd ? '$'+state.risk_usd.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : '--'}</span></div>
                                </div>`;
                                    
                        if (state.status === 'IN_TRADE' && state.entry_price && state.stop_loss && state.take_profit) {
                            let sl = parseFloat(state.stop_loss);
                            let tp = parseFloat(state.take_profit);
                            let isLong = state.position === 'BUY';
                            let range = Math.abs(tp - sl);
                            let assetPrice = globalPrices[asset] && globalPrices[asset] !== 0 ? globalPrices[asset] : parseFloat(state.entry_price);
                            let currentDist = isLong ? (assetPrice - sl) : (sl - assetPrice);
                            let pct = 0;
                            if (range !== 0) { pct = (currentDist / range) * 100; }
                            pct = Math.max(0, Math.min(100, pct));
                            let isWin = (isLong && assetPrice > state.entry_price) || (!isLong && assetPrice < state.entry_price);
                            let cursorColor = isWin ? '#00ff00' : '#ff4444';
                            
                            let diff = isLong ? (assetPrice - parseFloat(state.entry_price)) : (parseFloat(state.entry_price) - assetPrice);
                            let unPnl = diff * (state.size_btc || 0);
                            globalUnrealizedPnl += unPnl;
                            activeTradesCount += 1;
                            
                            let margin = state.size_usd / (state.leverage || 1);
                            let unPnlPct = margin ? (unPnl / margin) * 100 : 0;
                            let unPnlStr = (unPnl >= 0 ? '+' : '') + '$' + Math.abs(unPnl).toFixed(2) + ' (' + (unPnl >= 0 ? '+' : '') + unPnlPct.toFixed(2) + '%)';
                            let unPnlColor = unPnl >= 0 ? '#00ff00' : '#ff0000';

                            assetGrid += `
                            <div class="row" style="margin-top:10px; padding-top:10px; border-top: 1px solid #333;"><span class="label">U/PNL</span><span class="value" style="color:${unPnlColor}; font-size:13px;">${unPnlStr}</span></div>
                            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px dashed #333;">
                                <div style="display: flex; justify-content: space-between; font-size: 10px; margin-bottom: 4px; color: #ffb200;">
                                    <span style="color:#ff4444;">SL: $${sl.toLocaleString(undefined, {maximumFractionDigits:0})}</span>
                                    <span style="color:#00ff00;">TP: $${tp.toLocaleString(undefined, {maximumFractionDigits:0})}</span>
                                </div>
                                <div style="width: 100%; background: #222; height: 6px; border-radius: 3px; position: relative;">
                                    <div style="position: absolute; left: 0; top: 0; height: 100%; width: 100%; background: linear-gradient(90deg, #ff4444, #555, #00ff00); border-radius: 3px; opacity: 0.3;"></div>
                                    <div style="position: absolute; left: ${pct}%; top: -2px; width: 3px; height: 10px; background: ${cursorColor}; box-shadow: 0 0 5px ${cursorColor}; transition: left 0.5s ease-out;"></div>
                                </div>
                            </div>`;
                        }
                        assetGrid += `</div></div>`;
                    }
                    assetGrid += `</div>`;
                    htmlGrid += assetGrid;
                }
                
                // HOLDINGS
                htmlGrid += `<div class="bot-column">
                    <h2>HOLDINGS</h2>
                    <div class="bot-card" style="border: 1px solid #00ff00; background: rgba(0,255,0,0.02);">
                        <div class="bot-header" style="color: #00ff00; border-bottom: 1px solid #00ff00;">
                            <span>[ HOLDINGS ]</span>
                            <span class="status-badge status-active">LIVE</span>
                        </div>
                        <div class="bot-body" id="portfolio-body" style="padding: 15px;">
                            ${lastPortfolioHtml}
                        </div>
                    </div>
                </div>`;
                
                document.getElementById('main-grid').innerHTML = htmlGrid;

                let allTrades = [];
                for (let asset in fleet) {
                    for (let tf in fleet[asset]) {
                        if (fleet[asset][tf].recent_trades) {
                            fleet[asset][tf].recent_trades.forEach(t => {
                                allTrades.push({ asset, tf, ...t });
                            });
                        }
                    }
                }
                
                // Sort by time descending
                allTrades.sort((a, b) => new Date(b.time) - new Date(a.time));
                
                let histHtml = '<table class="history-table"><tr><th>TIME</th><th>PAIR</th><th>TYPE</th><th>PRICE</th><th>PNL & REASON</th></tr>';
                
                allTrades.slice(0, 30).forEach(t => {
                    let pnlColor = t.pnl > 0 ? '#00ff00' : (t.pnl < 0 ? '#ff0000' : '#ffb200');
                    let pnlStr = t.pnl !== 0 ? (t.pnl > 0 ? '+' : '') + '$' + Math.abs(t.pnl).toFixed(2) : '--';
                    
                    let typeStr = t.type.includes('COMPRA') ? 'LONG' : 'SHRT';
                    let typeColor = t.type.includes('COMPRA') ? '#00ff00' : '#ff0000';
                    let action = t.type.includes('Apertura') ? 'OPN' : 'CLS';
                    
                    let timeParts = t.time.split(' ');
                    let timeStr = timeParts.length > 1 ? timeParts[1].substring(0,5) : t.time;
                    
                    let priceStr = '$' + t.price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits:2});
                    
                    let reasonStr = t.reason.replace(' (Trend)', '').replace(' (Counter-Trend)', '').replace(' (Justicia Histórica)', '');
                    
                    histHtml += `<tr>
                        <td>${timeStr}</td>
                        <td style="font-weight:bold; color:#ffffff;">${t.asset}<br><span style="font-size:11px; color:#ffffff; font-weight:normal;">${t.tf}</span></td>
                        <td style="color:${typeColor};">${typeStr}<br><span style="font-size:11px; color:#ffffff; font-weight:normal;">${action}</span></td>
                        <td>${priceStr}</td>
                        <td style="color:${pnlColor}; font-weight:bold;">${pnlStr}<br><span style="font-size:11px; color:#FFCC00; font-weight:bold;">${reasonStr}</span></td>
                    </tr>`;
                });
                histHtml += '</table>';
                
                let histEl = document.getElementById('history-content');
                if (histEl) histEl.innerHTML = histHtml;

                let totalEquity = globalEquity + globalUnrealizedPnl;
                let baseEquity = activeBotsCount * 10000; // Dynamic based on active bots (e.g. 9 bots * 10k)
                if (baseEquity === 0) baseEquity = 10000;
                let roiPct = ((totalEquity - baseEquity) / baseEquity) * 100;
                let roiColor = roiPct >= 0 ? '#00ff00' : '#ff0000';
                let roiStr = (roiPct >= 0 ? '+' : '') + roiPct.toFixed(2) + '%';
                
                document.getElementById('global-equity').innerHTML = `$${totalEquity.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} <span style="color:${roiColor}; font-size:12px;">(${roiStr})</span>`;
                
                let pnlSumStr = (globalUnrealizedPnl >= 0 ? '+' : '') + '$' + Math.abs(globalUnrealizedPnl).toFixed(2);
                let pnlSumColor = globalUnrealizedPnl >= 0 ? '#00ff00' : '#ff0000';
                
                let pnlEl = document.getElementById('global-pnl');
                if (!pnlEl) {
                    let headerInfo = document.querySelector('.top-bar').nextElementSibling;
                    let newEl = document.createElement('div');
                    newEl.id = 'global-pnl';
                    newEl.style.textAlign = 'center';
                    newEl.style.marginBottom = '15px';
                    newEl.style.fontWeight = 'bold';
                    newEl.style.fontSize = '14px';
                    headerInfo.parentNode.insertBefore(newEl, headerInfo.nextSibling);
                    pnlEl = newEl;
                }
                if (activeTradesCount > 0) {
                    pnlEl.innerHTML = `ACTIVE: <span style="color:#ffffff">${activeTradesCount}</span> &nbsp;|&nbsp; TOTAL: <span style="color:#ffffff">${Math.floor(totalHistoricalTrades)}</span> &nbsp;|&nbsp; U/PNL: <span style="color:${pnlSumColor}">${pnlSumStr}</span>`;
                } else {
                    pnlEl.innerHTML = `ACTIVE: <span style="color:#ffffff">0</span> &nbsp;|&nbsp; TOTAL: <span style="color:#ffffff">${Math.floor(totalHistoricalTrades)}</span>`;
                }

                
            } catch (e) { document.getElementById('macro-context').innerHTML = '<span style="color:red">' + e.message + '</span>';  document.getElementById('macro-context').innerHTML = '<span style="color:red">' + e.message + '</span>'; }
        }

        setInterval(fetchSystem, 5000);
        setInterval(fetchPrices, 2000);
        setInterval(fetchPortfolio, 30000); // 30 segundos
        setInterval(fetchFnG, 600000); // 10 minutes for F&G
        
        fetchSystem();
        fetchPrices();
        fetchPortfolio();
        fetchFnG();
        
        // --- WebSockets ---
        const socket = io();
        socket.on('terminal_log', function(data) {
            let tc = document.getElementById('terminal-content');
            if(tc) {
                // Clear the default text on first load
                if(tc.innerHTML.includes('SYSTEM INITIALIZATION')) { tc.innerHTML = ''; }
                let lines = tc.innerHTML.split('<br>').filter(l => l.trim() !== '');
                let msg = data.msg;
                msg = msg.replace(/Analizando/g, 'Analyzing');
                msg = msg.replace(/con Inteligencia Cuantitativa/g, 'via Quantitative Core');
                msg = msg.replace(/Precio:/g, 'Price:');
                msg = msg.replace(/en/g, 'on'); // 'Analizando BTC en 5m' -> 'Analyzing BTC on 5m'
                lines.push('> ' + msg);
                if(lines.length > 9) lines.shift();
                tc.innerHTML = lines.join('<br>');
            }
        });

        socket.on('fleet_update', function(data) {
            currentFleet = data;
            renderFleet(data);
        });
