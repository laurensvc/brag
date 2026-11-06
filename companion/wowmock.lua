-- Just enough of the WoW API to run Brag.lua outside the game; fakewow.py drives it.
-- Frames only have the methods Brag uses, so calling anything else errors, as a typo would in game.
-- HOST (set by fakewow.py): screen = {w, h}, uiScale, player = {name, surname, class, level, zone},
-- itemCache = {[itemID] = {name, quality}} (the item cache), screenshot(), time().

local timers, now = {}, 0
local registry = {} -- every frame and texture, for events, rendering and finding panel widgets

C_Timer = { After = function(delay, fn) timers[#timers + 1] = { at = now + delay, fn = fn } end }

function MOCK_advance(seconds) -- run due timers in order, including ones they schedule
  local target = now + seconds
  while true do
    local best
    for i, t in ipairs(timers) do
      if t.at <= target and (not best or t.at < timers[best].at) then best = i end
    end
    if not best then break end
    local t = table.remove(timers, best)
    now = t.at
    t.fn()
  end
  now = target
end

function MOCK_now() return now end

function MOCK_fire(event, ...)
  for _, f in ipairs(registry) do
    if f.events and f.events[event] and f.scripts.OnEvent then f.scripts.OnEvent(f, event, ...) end
  end
end

-- Regions --------------------------------------------------------------------------------------

local Region = {}
Region.__index = Region

local function newRegion(kind, parent, extra)
  local r = setmetatable({ kind = kind, parent = parent, shown = true, scale = 1, points = {}, scripts = {} }, Region)
  for k, v in pairs(extra or {}) do r[k] = v end
  registry[#registry + 1] = r
  return r
end

function Region:SetSize(w, h) self.width, self.height = w, h end
function Region:SetWidth(w) self.width = w end
function Region:SetHeight(h) self.height = h end
function Region:ClearAllPoints() self.points = {} end
function Region:SetPoint(point, a, b, c, d)
  local rel, relPoint, x, y = self.parent, point, 0, 0
  if type(a) == "number" then
    x, y = a, b or 0
  elseif type(a) == "table" then
    rel = a
    if type(b) == "string" then relPoint, x, y = b, c or 0, d or 0 else x, y = b or 0, c or 0 end
  end
  self.points[#self.points + 1] = { point = point, rel = rel, relPoint = relPoint, x = x, y = y }
end
function Region:Show() self.shown = true end
function Region:Hide()
  self.shown = false
  if self.scripts.OnHide then self.scripts.OnHide(self) end
end
function Region:IsShown() return self.shown end
function Region:SetShown(shown) if shown then self:Show() else self:Hide() end end
function Region:IsVisible() return self.shown and (not self.parent or self.parent:IsVisible()) end
function Region:GetEffectiveScale() return self.scale * (self.parent and self.parent:GetEffectiveScale() or 1) end

-- Frames
function Region:SetScale(s) self.scale = s end
function Region:SetFrameStrata(s) self.strata = s end
function Region:SetMovable() end
function Region:EnableMouse() end
function Region:RegisterForDrag() end
function Region:StartMoving() end
function Region:StopMovingOrSizing() end
function Region:SetScript(name, fn) self.scripts[name] = fn end
function Region:GetScript(name) return self.scripts[name] end
function Region:RegisterEvent(e) self.events[e] = true end
function Region:CreateTexture() return newRegion("Texture", self, { isTexture = true }) end
function Region:CreateFontString() return newRegion("FontString", self) end

-- Textures, font strings, buttons, edit boxes
function Region:SetColorTexture(r, g, b, a) self.color = { r, g, b, a or 1 } end
function Region:SetText(text)
  self.text = text
  if self.kind == "EditBox" and self.scripts.OnTextChanged then self.scripts.OnTextChanged(self, false) end
end
function Region:GetText() return self.text or "" end
function Region:SetJustifyH() end
function Region:SetChecked(c) self.checked = c and true or false end
function Region:GetChecked() return self.checked end
function Region:SetAutoFocus() end
function Region:SetCursorPosition() end
function Region:ClearFocus() end
function Region:Click() if self.scripts.OnClick then self.scripts.OnClick(self, "LeftButton") end end

function CreateFrame(kind, name, parent)
  local f = newRegion(kind, parent, { events = {} })
  if name then _G[name] = f end
  return f -- template children (TitleText and so on) are left out: Brag checks for them
end

UIParent = newRegion("Frame", nil, { events = {} })
UIParent.scale = HOST.uiScale

-- Globals and API ------------------------------------------------------------------------------

tinsert, tremove = table.insert, table.remove
function strtrim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
function time() return math.floor(HOST.time()) end
function GetPhysicalScreenSize() return HOST.screen.w, HOST.screen.h end
function UnitName() return HOST.player.name, HOST.player.surname end  -- Forever: the surname
function UnitClass() return HOST.player.class, HOST.player.class:upper(), 7 end
function UnitLevel() return HOST.player.level end
function GetRealZoneText() return HOST.player.zone end
function UnitGUID(unit) if unit == "player" then return "Player-1-00000001" end end
function GetTime() return now end
MOCK_combat = { n = 0 } -- the combat log event being fired, set by MOCK_combatLog
function CombatLogGetCurrentEventInfo() return unpack(MOCK_combat, 1, MOCK_combat.n) end
function MOCK_combatLog(...)
  MOCK_combat = { n = select("#", ...), ... }
  MOCK_fire("COMBAT_LOG_EVENT_UNFILTERED")
end
function GetTitleText() return MOCK_questTitle end
function ReloadUI() MOCK_reloaded = true end
function Screenshot()
  HOST.screenshot()
  C_Timer.After(0.05, function() MOCK_fire("SCREENSHOT_SUCCEEDED") end) -- the game confirms a frame later
end

LOOT_ITEM_SELF = "You receive loot: %s."
LOOT_ITEM_PUSHED_SELF = "You receive item: %s."
ITEM_QUALITY_COLORS = {}
for q, hex in pairs({ [0] = "9d9d9d", "ffffff", "1eff00", "0070dd", "a335ee", "ff8000", "e6cc80" }) do
  ITEM_QUALITY_COLORS[q] = { hex = "|cff" .. hex }
end
function GetItemInfo(link)
  local item = HOST.itemCache[tonumber(tostring(link):match("item:(%d+)"))]
  if item then return item.name, link, item.quality end -- nil when not cached, like the real thing
end

RaidWarningFrame = {}
ChatTypeInfo = { RAID_WARNING = { r = 1, g = 0.28, b = 0 } }
MOCK_banners = {}
function RaidNotice_AddMessage(_, text) MOCK_banners[#MOCK_banners + 1] = { text = text, at = now } end
UISpecialFrames, SlashCmdList = {}, {}

-- For fakewow.py -------------------------------------------------------------------------------

-- Pixel rectangles of every visible colored texture: {x, y, w, h, r, g, b}. Only TOPLEFT-to-TOPLEFT
-- anchors are resolved, which is all the strip uses.
local function topleft(r)
  if r == UIParent then return 0, 0 end
  local p = r.points[1]
  if not p or p.point ~= "TOPLEFT" or p.relPoint ~= "TOPLEFT" then return nil end
  local rx, ry = topleft(p.rel)
  if not rx then return nil end
  local px = (r.isTexture and r.parent or r):GetEffectiveScale() * HOST.screen.h / 768
  return rx + p.x * px, ry - p.y * px
end

function MOCK_render()
  local out = {}
  for _, r in ipairs(registry) do
    if r.isTexture and r.color and r:IsVisible() then
      local x, y = topleft(r)
      local px = r.parent:GetEffectiveScale() * HOST.screen.h / 768
      if x then out[#out + 1] = { x, y, r.width * px, r.height * px, unpack(r.color) } end
    end
  end
  return out
end

function MOCK_find(kind, text) -- a widget by type and label, to click buttons in the /brag panel
  for _, r in ipairs(registry) do
    if r.kind == kind and (not text or r.text == text) and r:IsVisible() then return r end
  end
end
