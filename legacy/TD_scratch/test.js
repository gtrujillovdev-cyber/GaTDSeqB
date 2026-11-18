    <script>
        async function fetchSystem() {
            try {
                let res = await fetch('/api/system');
                let data = await res.json();
                document.getElementById('sys-cpu').innerText = `${data.cpu}%`;
                document.getElementById('sys-ram').innerText = `${data.ram}%`;
                document.getElementById('sys-temp').innerText = `${data.temp}°C`;
            } catch(e) {}
        }
        
        let lastPrice = 0;
        async function fetchBTC() {
            try {
                let res = await fetch('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT');
                let data = await res.json();
                let price = parseFloat(data.price);
                let priceEl = document.getElementById('btc-price');
                priceEl.innerText = `$${price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                if (price > lastPrice && lastPrice !== 0) { priceEl.style.color = '#00ff00'; priceEl.style.textShadow = '0 0 25px rgba(0,255,0,0.4)'; }
                else if (price < lastPrice) { priceEl.style.color = '#ff3333'; priceEl.style.textShadow = '0 0 25px rgba(255,51,51,0.4)'; }
                lastPrice = price;
            } catch(e) {}
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
        let lastPortfolioHtml = '<div style="text-align:center; color:#ffb200; margin-top:20px; font-size:11px;">CARGANDO DATOS...</div>';
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
                                    <span>Compra: $${asset.entry_price.toLocaleString(undefined, {maximumFractionDigits: 8})}</span>
                                </div>
                            `;
                        } else {
                            pnlStr = `<span style="color:#00ffff;">Spot</span>`;
                        }
                        
                        pfHtml += `
                        <div class="row" style="display:flex; flex-direction:column; margin-bottom: 12px; border-bottom: 1px dotted #151515; padding-bottom:10px;">
                            <div style="display:flex; justify-content:space-between; width:100%; margin-bottom:4px;">
                                <span style="font-weight:bold;">${symbol}</span>
                                <span>$${currentPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; width:100%; font-size:12px; color:#ffb200; align-items:center;">
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
                                <span>Margen: $${asset.margin.toLocaleString(undefined, {maximumFractionDigits: 2})}</span>
                                <span>C: $${asset.entry_price.toLocaleString(undefined, {maximumFractionDigits: 8})}${asset.liq_price ? ' <span style="margin:0 4px;">|</span> <span style="color:#ff6b6b">Liq: $'+asset.liq_price.toLocaleString(undefined, {maximumFractionDigits: 8})+'</span>' : ''}</span>
                            </div>
                        `;
                        
                        pfHtml += `
                        <div class="row" style="display:flex; flex-direction:column; margin-bottom: 12px; border-bottom: 1px dotted #151515; padding-bottom:10px;">
                            <div style="display:flex; justify-content:space-between; width:100%; margin-bottom:4px;">
                                <span style="font-weight:bold; color:#00ff00;">${symbol} LONG</span>
                                <span>$${currentPrice.toLocaleString(undefined, {minimumFractionDigits: 4, maximumFractionDigits: 8})}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; width:100%; font-size:12px; color:#ffb200; align-items:center;">
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
                    <div style="font-size:11px; color:#ffb200; margin-bottom:5px;">NET WORTH EST.</div>
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
                
                for (const asset of ['BTC', 'ETH', 'HYPE']) {
                    let assetGrid = `<div class="bot-column"><h2 style="color: #ffb84d; border-bottom: 1px solid #333; padding-bottom: 5px; margin-bottom: 10px; text-align: center;">${asset}</h2>`;
                    
                    if (!fleet[asset]) continue;
                    
                    for (const tf of ['5m', '15m', '1h', '4h', '1d']) {
                        const state = fleet[asset][tf];
                        if (!state) continue;
                        globalEquity += state.bank || 10000.0;
                        
                        let badgeClass = 'status-offline';
                        let badgeText = 'OFFLINE';
                        if (state.status === 'IN_TRADE') { badgeClass = 'status-active'; badgeText = 'IN TRADE'; }
                        else if (state.status === 'IDLE') { badgeClass = 'status-idle'; badgeText = 'IDLE'; }
                        
                        let tdColor = state.td_count > 0 ? 'val-red' : (state.td_count < 0 ? 'val-green' : '');
                        
                        if (state.status !== 'IN_TRADE') {
                            assetGrid += `
                                <div class="bot-card" style="margin-bottom: 5px; padding: 8px;">
                                    <div class="bot-header" style="border: none; padding: 0;">
                                        <span>[ ${tf} ]</span>
                                        <div style="display:flex; gap:10px;">
                                            <span style="font-size: 11px;">TD: <span class="${tdColor}">${state.td_count !== undefined ? state.td_count : '--'}</span></span>
                                            <span class="status-badge ${badgeClass}">${badgeText}</span>
                                        </div>
                                    </div>
                                </div>
                            `;
                            continue;
                        }
                        
                        assetGrid += `
                            <div class="bot-card">
                                <div class="bot-header">
                                    <span>[ ${tf} ]</span>
                                    <span class="status-badge ${badgeClass}">${badgeText}</span>
                                </div>
                                <div class="bot-body">
                                    <div class="row"><span class="label">Bankroll</span><span class="value val-green">$${state.bank ? state.bank.toLocaleString(undefined, {minimumFractionDigits: 2}) : '--'}</span></div>
                                    <div class="row"><span class="label">TD Count</span><span class="value ${tdColor}">${state.td_count !== undefined ? state.td_count : '--'}</span></div>
                                    <div class="row"><span class="label">Win Rate</span><span class="value">${state.win_rate ? state.win_rate.toFixed(1) : '0.0'}%</span></div>
                                    <div class="row"><span class="label">Max DD</span><span class="value val-red">-${state.drawdown ? state.drawdown.toFixed(2) : '0.00'}%</span></div>
                                    <div class="row"><span class="label">Position</span><span class="value ${state.position==='BUY'?'val-green':(state.position==='SELL'?'val-red':'')}">${state.position || 'NONE'}</span></div>
                                    <div class="row"><span class="label">Entry</span><span class="value">${state.entry_price ? '$'+state.entry_price.toLocaleString() : '--'}</span></div>
                                    <div class="row"><span class="label">Stop</span><span class="value">${state.stop_loss ? '$'+state.stop_loss.toLocaleString() : '--'}</span></div>
                                    <div class="row"><span class="label">Invest</span><span class="value">${state.size_usd ? '$'+state.size_usd.toLocaleString() : '--'}</span></div>
                                    <div class="row"><span class="label">Risk Exp.</span><span class="value">${state.risk_usd ? '$'+state.risk_usd.toLocaleString() : '--'}</span></div>`;
                                    
                        if (state.status === 'IN_TRADE' && state.entry_price && state.stop_loss && state.take_profit) {
                            let sl = parseFloat(state.stop_loss);
                            let tp = parseFloat(state.take_profit);
                            let isLong = state.position === 'BUY';
                            let range = Math.abs(tp - sl);
                            let assetPrice = asset === 'BTC' ? lastPrice : parseFloat(state.entry_price);
                            let currentDist = isLong ? (assetPrice - sl) : (sl - assetPrice);
                            let pct = 0;
                            if (range !== 0) { pct = (currentDist / range) * 100; }
                            pct = Math.max(0, Math.min(100, pct));
                            let isWin = (isLong && assetPrice > state.entry_price) || (!isLong && assetPrice < state.entry_price);
                            let cursorColor = isWin ? '#00ff00' : '#ff4444';
                            assetGrid += `
                            <div style="margin-top: 15px; padding-top: 10px; border-top: 1px dashed #333;">
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
                document.getElementById('global-equity').innerText = `$${globalEquity.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                
            } catch (e) {}
        }

        setInterval(fetchSystem, 5000);
        setInterval(fetchBTC, 2000);
        setInterval(fetchPortfolio, 30000); // 30 segundos
        setInterval(fetchFnG, 600000); // 10 minutes for F&G
        
        fetchSystem();
        fetchBTC();
        fetchPortfolio();
        fetchFnG();
        
        // --- WebSockets ---
        const socket = io();
        socket.on('fleet_update', function(data) {
            renderFleet(data);
        });
    </script>
