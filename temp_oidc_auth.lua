-- oidc_auth.lua (DEBUG MODE 13 - HARDCODED SECRET + SCHEME)
local openidc = require("resty.openidc")

local function validate()
    local scheme = ngx.var.scheme
    ngx.log(ngx.ERR, "[DEBUG_13] Scheme: " .. scheme .. " | URI: " .. ngx.var.uri)

    local client_id = os.getenv("OIDC_CLIENT_ID")
    local client_secret = os.getenv("OIDC_CLIENT_SECRET")
    
    -- [TEST] Hardcoded 32-byte secret to rule out ENV/Length issues
    local cookie_secret = "12345678901234567890123456789012" 
    
    local discovery_url = "http://ai4radmed-keycloak:8080/realms/ai4radmed/.well-known/openid-configuration"

    local opts = {
        redirect_uri_path = "/redirect_uri",
        discovery = discovery_url,
        client_id = client_id,
        client_secret = client_secret,
        redirect_uri_scheme = "https", 
        logout_path = "/logout",
        redirect_after_logout_uri = "/",
        
        session_contents = {name=true}, 
        session_storage = "cookie", 
        
        ssl_verify = "no",
        
        -- [Fix] Allow both Secure and Non-Secure contexts for debugging
        session_cookie_secure = false, 
        session_cookie_http_only = true,
        session_cookie_path = "/",
        session_cookie_samesite = "Lax",
        
        accept_bearer_token = true,
        iat_slack = 600,
        lifecycle_debug = true
    }
    
    local res, err = openidc.authenticate(opts, cookie_secret)

    if err then
        ngx.log(ngx.ERR, "[DEBUG_13] authenticate ERROR: " .. (err or "unknown"))
        ngx.status = 500
        ngx.say(err)
        ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    if not res then
         ngx.log(ngx.ERR, "[DEBUG_13] authenticate returned nil (Redirecting)")
    else
         ngx.log(ngx.ERR, "[DEBUG_13] authenticate SUCCESS!")
         if res.id_token then
             ngx.req.set_header("X-User-Email", res.id_token.email)
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
