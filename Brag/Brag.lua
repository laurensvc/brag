-- WoW addons can't touch the network, so we only show a banner and take a screenshot.
-- The companion script posts the screenshot, using the webhook saved here in BragDB.
local ADDON = ...
local DEFAULTS = {
  enabled = true, level = true, quest = true, loot = true, boss = true, death = true, minQuality = 4, webhook = "",
}
local QUALITY_NAMES = { [2] = "Uncommon", [3] = "Rare", [4] = "Epic", [5] = "Legendary" }
local GetItemInfo = C_Item and C_Item.GetItemInfo or GetItemInfo -- newer clients drop the global
local db

-- "You receive loot: %s." -> "You receive loot: " (localized by the client)
local lootPrefixes = {}
for _, fmt in ipairs({ LOOT_ITEM_SELF, LOOT_ITEM_PUSHED_SELF }) do
  table.insert(lootPrefixes, (fmt:match("^(.-)%%s")))
end

-- Data strip: WoW only writes files at logout, so the event details travel inside the screenshot.
-- Black/white blocks in the top-left corner; the companion decodes them and crops them off.
-- Layout (the companion's read_strip mirrors this): bits MSB first, row-major, BLOCK physical pixels each;
-- bytes = "Bg", blocks per row (2 bytes), payload length, payload, Fletcher-16 checksum (2 bytes).
local BLOCK = 8
local strip = CreateFrame("Frame", nil, UIParent)
strip:SetFrameStrata("TOOLTIP")
strip:SetPoint("TOPLEFT")
strip:Hide()
local blocks = {}

local function drawStrip(payload)
  local w, h = 1024, 768 -- the companion also finds the block size itself, so a fallback is fine
  if GetPhysicalScreenSize then w, h = GetPhysicalScreenSize() end
  local size = BLOCK * 768 / h / strip:GetEffectiveScale() -- at scale 1, one UI unit = 768 / screen height pixels
  local perRow = math.floor(w / BLOCK)
  local bytes = { 66, 103, math.floor(perRow / 256), perRow % 256, #payload }
  local s1, s2 = 0, 0
  for i = 1, #payload do
    local b = payload:byte(i)
    bytes[#bytes + 1] = b
    s1 = (s1 + b) % 255
    s2 = (s2 + s1) % 255
  end
  bytes[#bytes + 1] = s1
  bytes[#bytes + 1] = s2
  local n = 0
  for _, b in ipairs(bytes) do
    for bit = 7, 0, -1 do
      local on = math.floor(b / 2 ^ bit) % 2
      local t = blocks[n + 1] or strip:CreateTexture(nil, "OVERLAY")
      blocks[n + 1] = t
      t:ClearAllPoints()
      t:SetSize(size, size)
      t:SetPoint("TOPLEFT", (n % perRow) * size, -math.floor(n / perRow) * size)
      t:SetColorTexture(on, on, on, 1)
      t:Show()
      n = n + 1
    end
  end
  for i = n + 1, #blocks do blocks[i]:Hide() end
  strip:SetSize(perRow * size, math.ceil(n / perRow) * size)
  strip:Show()
end

local function clean(s)
  return (tostring(s or ""):gsub("[\t\r\n]", " "))
end

-- One screenshot at a time: a quest turn-in often levels you up too, and each needs its own strip.
local queue, current = {}, nil
local function nextShot()
  current = tremove(queue, 1)
  if not current then return strip:Hide() end
  RaidNotice_AddMessage(RaidWarningFrame, current.text, ChatTypeInfo["RAID_WARNING"])
  drawStrip(current.payload)
  local shot = current
  C_Timer.After(0.3, function() -- let the banner and strip render first
    if current ~= shot then return end
    shot.taken = true
    Screenshot()
    C_Timer.After(3, function() -- in case SCREENSHOT_SUCCEEDED never comes
      if current == shot then nextShot() end
    end)
  end)
end

-- kind: level | quest | loot | boss | death | test. detail: quest title, item name or boss name.
local function brag(kind, text, detail, quality, level)
  tinsert(BragHistory, { time = time(), text = text }) -- the companion app shows this history
  if #BragHistory > 500 then tremove(BragHistory, 1) end -- keep the saved file small
  local payload = table.concat({
    "1", kind, clean(UnitName("player")), clean((UnitClass("player"))), level or UnitLevel("player"),
    clean(GetRealZoneText()), clean(detail):sub(1, 120), quality or "",
  }, "\t"):sub(1, 250) -- the length has to fit in one byte
  tinsert(queue, { text = text, payload = payload })
  if not current then nextShot() end
end

-- Quality from the link's color, so items that aren't cached yet still count.
local function linkQuality(link)
  local q = link:match("^|cnIQ(%d):")
  if q then return tonumber(q) end
  local color = link:match("^|c(%x%x%x%x%x%x%x%x)")
  for quality, c in pairs(ITEM_QUALITY_COLORS) do
    if color and c.hex and c.hex:lower() == "|c" .. color:lower() then return quality end
  end
  return select(3, GetItemInfo(link))
end

local questTitle
local f = CreateFrame("Frame")
f:RegisterEvent("ADDON_LOADED")
f:RegisterEvent("PLAYER_LEVEL_UP")
f:RegisterEvent("QUEST_COMPLETE")
f:RegisterEvent("QUEST_TURNED_IN")
f:RegisterEvent("CHAT_MSG_LOOT")
f:RegisterEvent("ENCOUNTER_END")
f:RegisterEvent("PLAYER_DEAD")
f:RegisterEvent("SCREENSHOT_SUCCEEDED")
f:RegisterEvent("SCREENSHOT_FAILED")
f:SetScript("OnEvent", function(_, event, arg1, arg2, _, _, arg5)
  if event == "ADDON_LOADED" and arg1 == ADDON then
    BragDB = BragDB or {}
    BragHistory = BragHistory or {}
    for k, v in pairs(DEFAULTS) do
      if BragDB[k] == nil then BragDB[k] = v end
    end
    db = BragDB
  elseif event == "SCREENSHOT_SUCCEEDED" or event == "SCREENSHOT_FAILED" then
    if current and current.taken then nextShot() end -- ignores screenshots the player takes
  elseif not (db and db.enabled) then
    return
  elseif event == "PLAYER_LEVEL_UP" and db.level then
    brag("level", "Level " .. arg1 .. "!", nil, nil, arg1) -- UnitLevel still says the old level here
  elseif event == "QUEST_COMPLETE" then
    questTitle = GetTitleText() -- quest reward dialog is open; title is gone after turn-in
  elseif event == "QUEST_TURNED_IN" and db.quest then
    brag("quest", "Quest complete: " .. (questTitle or "?"), questTitle or "?")
    questTitle = nil
  elseif event == "CHAT_MSG_LOOT" and db.loot then
    for _, prefix in ipairs(lootPrefixes) do
      if arg1:find(prefix, 1, true) == 1 then
        local link = arg1:match("|c.-|Hitem:.-|h|r")
        local quality = link and linkQuality(link)
        if quality and quality >= db.minQuality then
          brag("loot", "Big drop: " .. link, link:match("|h%[(.-)%]|h"), quality)
        end
        return
      end
    end
  elseif event == "ENCOUNTER_END" and db.boss and arg5 == 1 then -- encounterID, name, difficulty, size, success
    brag("boss", "Boss defeated: " .. (arg2 or "?"), arg2 or "?")
  elseif event == "PLAYER_DEAD" and db.death then
    brag("death", "Died in " .. GetRealZoneText(), nil)
  end
end)

-- Settings window (/brag)
local panel
local function buildPanel()
  local p = CreateFrame("Frame", "BragPanel", UIParent, "BasicFrameTemplateWithInset")
  p:SetSize(380, 366)
  p:SetPoint("CENTER")
  p:SetMovable(true)
  p:EnableMouse(true)
  p:RegisterForDrag("LeftButton")
  p:SetScript("OnDragStart", p.StartMoving)
  p:SetScript("OnDragStop", p.StopMovingOrSizing)
  tinsert(UISpecialFrames, "BragPanel") -- Escape closes it
  if p.TitleText then p.TitleText:SetText("Brag") end

  local function text(parent, template, s)
    local t = parent:CreateFontString(nil, "OVERLAY", template)
    t:SetText(s)
    return t
  end

  local y = -32
  local function checkbox(label, key)
    local c = CreateFrame("CheckButton", nil, p, "UICheckButtonTemplate")
    c:SetPoint("TOPLEFT", 16, y)
    c:SetChecked(db[key])
    c:SetScript("OnClick", function(self) db[key] = self:GetChecked() and true or false end)
    text(c, "GameFontHighlight", label):SetPoint("LEFT", c, "RIGHT", 2, 0)
    y = y - 28
    return c
  end
  checkbox("Enabled", "enabled")
  checkbox("Level ups", "level")
  checkbox("Quest turn-ins", "quest")
  local loot = checkbox("Loot", "loot")
  checkbox("Boss kills", "boss")
  checkbox("Deaths", "death")

  local q = CreateFrame("Button", nil, p, "UIPanelButtonTemplate")
  q:SetSize(170, 22)
  q:SetPoint("LEFT", loot, "RIGHT", 90, 0)
  local function qualityLabel()
    q:SetText("At least: " .. ITEM_QUALITY_COLORS[db.minQuality].hex .. QUALITY_NAMES[db.minQuality] .. "|r")
  end
  q:SetScript("OnClick", function()
    db.minQuality = db.minQuality >= 5 and 2 or db.minQuality + 1
    qualityLabel()
  end)
  qualityLabel()

  text(p, "GameFontNormal", "Discord webhook URL"):SetPoint("TOPLEFT", 20, y - 10)
  local e = CreateFrame("EditBox", nil, p, "InputBoxTemplate")
  e:SetSize(336, 20)
  e:SetPoint("TOPLEFT", 24, y - 28)
  e:SetAutoFocus(false)
  local warn = text(p, "GameFontRed", "")
  warn:SetPoint("TOPLEFT", 20, y - 52)
  e:SetScript("OnTextChanged", function(self)
    db.webhook = strtrim(self:GetText())
    local bad = db.webhook ~= "" and not db.webhook:find("/api/webhooks/", 1, true)
    warn:SetText(bad and "That doesn't look like a Discord webhook URL" or "")
  end)
  e:SetScript("OnEnterPressed", e.ClearFocus)
  e:SetScript("OnEscapePressed", e.ClearFocus)
  e:SetText(db.webhook)
  e:SetCursorPosition(0)
  local hint = text(p, "GameFontDisableSmall",
    "Easier: paste it in the Brag app instead (its link wins). Here: Discord Server Settings > Integrations > Webhooks > New Webhook > Copy URL, then Ctrl+V.\nThe app sees changes here after Save & reload.")
  hint:SetPoint("TOPLEFT", 20, y - 68)
  hint:SetWidth(340)
  hint:SetJustifyH("LEFT")

  local save = CreateFrame("Button", nil, p, "UIPanelButtonTemplate")
  save:SetSize(120, 22)
  save:SetPoint("BOTTOMRIGHT", -14, 12)
  save:SetText("Save & reload")
  save:SetScript("OnClick", ReloadUI) -- SavedVariables are only written to disk on reload/logout

  local test = CreateFrame("Button", nil, p, "UIPanelButtonTemplate")
  test:SetSize(120, 22)
  test:SetPoint("BOTTOMLEFT", 14, 12)
  test:SetText("Test post")
  test:SetScript("OnClick", function()
    p:Hide()
    brag("test", "Brag test: if this shows up in Discord, you're all set!")
  end)
  p:Hide() -- new frames start shown; /brag toggles it right after building
  return p
end

SLASH_BRAG1 = "/brag"
SlashCmdList.BRAG = function()
  panel = panel or buildPanel()
  panel:SetShown(not panel:IsShown())
end
