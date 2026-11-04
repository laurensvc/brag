-- WoW addons can't touch the network, so we only show a banner and take a screenshot.
-- The companion script posts the screenshot, using the webhook saved here in BragDB.
local ADDON = ...
local DEFAULTS = { enabled = true, level = true, quest = true, loot = true, minQuality = 4, webhook = "" }
local QUALITY_NAMES = { [2] = "Uncommon", [3] = "Rare", [4] = "Epic", [5] = "Legendary" }
local GetItemInfo = C_Item and C_Item.GetItemInfo or GetItemInfo -- newer clients drop the global
local db

-- "You receive loot: %s." -> "You receive loot: " (localized by the client)
local lootPrefixes = {}
for _, fmt in ipairs({ LOOT_ITEM_SELF, LOOT_ITEM_PUSHED_SELF }) do
  table.insert(lootPrefixes, (fmt:match("^(.-)%%s")))
end

local function brag(text)
  tinsert(BragHistory, { time = time(), text = text }) -- the companion app shows this history
  if #BragHistory > 500 then tremove(BragHistory, 1) end -- keep the saved file small
  RaidNotice_AddMessage(RaidWarningFrame, text, ChatTypeInfo["RAID_WARNING"])
  C_Timer.After(0.3, Screenshot) -- let the banner render first
end

local questTitle
local f = CreateFrame("Frame")
f:RegisterEvent("ADDON_LOADED")
f:RegisterEvent("PLAYER_LEVEL_UP")
f:RegisterEvent("QUEST_COMPLETE")
f:RegisterEvent("QUEST_TURNED_IN")
f:RegisterEvent("CHAT_MSG_LOOT")
f:SetScript("OnEvent", function(_, event, arg1)
  if event == "ADDON_LOADED" and arg1 == ADDON then
    BragDB = BragDB or {}
    BragHistory = BragHistory or {}
    for k, v in pairs(DEFAULTS) do
      if BragDB[k] == nil then BragDB[k] = v end
    end
    db = BragDB
  elseif not (db and db.enabled) then
    return
  elseif event == "PLAYER_LEVEL_UP" and db.level then
    brag("Level " .. arg1 .. "!")
  elseif event == "QUEST_COMPLETE" then
    questTitle = GetTitleText() -- quest reward dialog is open; title is gone after turn-in
  elseif event == "QUEST_TURNED_IN" and db.quest then
    brag("Quest complete: " .. (questTitle or "?"))
    questTitle = nil
  elseif event == "CHAT_MSG_LOOT" and db.loot then
    for _, prefix in ipairs(lootPrefixes) do
      if arg1:find(prefix, 1, true) == 1 then
        local item = arg1:match("|H(item:[^|]+)|h")
        -- shortcut: uncached items return nil and are skipped; looted items are almost always cached
        local _, link, quality = GetItemInfo(item or "")
        if quality and quality >= db.minQuality then brag("Big drop: " .. link) end
        return
      end
    end
  end
end)

-- Settings window (/brag)
local panel
local function buildPanel()
  local p = CreateFrame("Frame", "BragPanel", UIParent, "BasicFrameTemplateWithInset")
  p:SetSize(380, 290)
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
    "In Discord: Server Settings > Integrations > Webhooks > New Webhook > Copy URL, then paste here (Ctrl+V).\nThe companion sees changes after Save & reload.")
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
    brag("Brag test: if this shows up in Discord, you're all set!")
  end)
  return p
end

SLASH_BRAG1 = "/brag"
SlashCmdList.BRAG = function()
  panel = panel or buildPanel()
  panel:SetShown(not panel:IsShown())
end
