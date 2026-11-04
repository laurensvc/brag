-- WoW addons can't touch the network, so we only show a banner and take a screenshot.
-- companion/watch.py picks the screenshot up and posts it to Discord.
local MIN_QUALITY = 4 -- 2 uncommon, 3 rare, 4 epic, 5 legendary
local GetItemInfo = C_Item and C_Item.GetItemInfo or GetItemInfo -- newer clients drop the global

-- "You receive loot: %s." -> "You receive loot: " (localized by the client)
local lootPrefixes = {}
for _, fmt in ipairs({ LOOT_ITEM_SELF, LOOT_ITEM_PUSHED_SELF }) do
  table.insert(lootPrefixes, (fmt:match("^(.-)%%s")))
end

local function brag(text)
  RaidNotice_AddMessage(RaidWarningFrame, text, ChatTypeInfo["RAID_WARNING"])
  C_Timer.After(0.3, Screenshot) -- let the banner render first
end

local questTitle
local f = CreateFrame("Frame")
f:RegisterEvent("PLAYER_LEVEL_UP")
f:RegisterEvent("QUEST_COMPLETE")
f:RegisterEvent("QUEST_TURNED_IN")
f:RegisterEvent("CHAT_MSG_LOOT")
f:SetScript("OnEvent", function(_, event, arg1)
  if event == "PLAYER_LEVEL_UP" then
    brag("Level " .. arg1 .. "!")
  elseif event == "QUEST_COMPLETE" then
    questTitle = GetTitleText() -- quest reward dialog is open; title is gone after turn-in
  elseif event == "QUEST_TURNED_IN" then
    brag("Quest complete: " .. (questTitle or "?"))
    questTitle = nil
  elseif event == "CHAT_MSG_LOOT" then
    for _, prefix in ipairs(lootPrefixes) do
      if arg1:find(prefix, 1, true) == 1 then
        local item = arg1:match("|H(item:[^|]+)|h")
        -- shortcut: uncached items return nil and are skipped; looted items are almost always cached
        local _, link, quality = GetItemInfo(item or "")
        if quality and quality >= MIN_QUALITY then brag("Big drop: " .. link) end
        return
      end
    end
  end
end)
