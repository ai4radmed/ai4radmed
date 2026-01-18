-- oidc_auth.lua (DEBUG MODE 13 - HARDCODED SECRET + SCHEME)
local openidc = require("resty.openidc")

local function validate()
    local scheme = ngx.var.scheme
    local raw_cookie = ngx.var.http_cookie or "nil"
    ngx.log(ngx.ERR, "[DEBUG_16] URI: " .. ngx.var.uri .. " | Cookie Header: " .. raw_cookie)
    
    local client_id = os.getenv("OIDC_CLIENT_ID")
    local client_secret = os.getenv("OIDC_CLIENT_SECRET")
    local cookie_secret = os.getenv("OIDC_COOKIE_SECRET")
    
    if cookie_secret then
        ngx.log(ngx.ERR, "[DEBUG_16] Cookie Secret Length: " .. #cookie_secret)
    else
        ngx.log(ngx.ERR, "[DEBUG_16] Cookie Secret is NIL!")
    end
    
    local discovery_url = "http://ai4radmed-keycloak:8080/realms/ai4radmed/.well-known/openid-configuration"

        -- OIDC Configuration
        redirect_uri = "https://vault.ai4radmed.internal/redirect_uri",
        -- redirect_uri_path = "/redirect_uri", -- Removed to fix deprecation warning
        discovery = discovery_url,
        client_id = client_id,
        client_secret = client_secret,
        scope = "openid email profile",
        
        -- Logout Configuration
        logout_path = "/logout",
        redirect_after_logout_uri = "/",
        
        -- OpenIDC specific options
        accept_bearer_token = true,
        iat_slack = 600,
        ssl_verify = "no",
        
        -- [Fix] lua-resty-session v4 Configuration (FLAT)
        cookie_name = "session",      -- MUST match lua-resty-openidc default!
        secret = cookie_secret,
        storage = "cookie",                -- Use Cookie for storage (Stateless)
        
        -- Flat Cookie Options (Required by v4 implementation)
        cookie_secure = true,
        cookie_http_only = true,
        cookie_path = "/",
        cookie_same_site = "Lax",
        cookie_max_age = 3600,
        
        cipher = "aes-256-gcm",
        audience = "ai4radmed-app",
    }
    
    -- [Fix] Correct API Call: authenticate(opts, target_url, session_opts)
    -- We pass nil for target_url (auto-detect) and nil for session_opts (use opts)
    local res, err = openidc.authenticate(opts)

    if err then
        ngx.log(ngx.ERR, "[DEBUG_17] authenticate ERROR: " .. (err or "unknown"))
        ngx.status = 500
        ngx.say(err)
        ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    if not res then
         ngx.log(ngx.ERR, "[DEBUG_17] authenticate returned nil (Redirecting)")
         -- Note: The library handles the 302 redirect here
    else
         ngx.log(ngx.ERR, "[DEBUG_17] authenticate SUCCESS!")
         if res.id_token then
             ngx.req.set_header("X-User-Email", res.id_token.email)
             ngx.log(ngx.ERR, "[DEBUG_17] Email: " .. (res.id_token.email or "nil"))
         end
         if ngx.var.uri == "/redirect_uri" then
             return ngx.redirect("/")
         end
    end
end

local function has_role(role) return false end
local function require_role(role) end

return {
    validate = validate,
    require_role = require_role,
    has_role = has_role
}
